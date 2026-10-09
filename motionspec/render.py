"""Project loading and rendering. A Project turns a validated spec into frames; render_video fans frames out across
processes (they are independent, so the speed-up is close to linear) and streams them in order into one ffmpeg process."""
import copy
import dataclasses
import hashlib
import json
import math
import multiprocessing as mp
import os
import subprocess
import sys
import tempfile
import threading
import time

from PIL import Image, ImageDraw

from . import align as align_mod, audio, autotime, backdrop, captions as captions_mod, paths
from .canvas import Canvas
from .constants import FPS
from .ease import in_out, prog
from .layout import get_format
from .post import LOOKS, MOTION, apply_camera, apply_punch, average, post
from .scenes import REGISTRY, load_builtin, load_plugins
from .theme import load_theme, mix
from .validate import validate

XF = 0.3  # default crossfade seconds


class SpecError(ValueError):
    """The spec failed validation. str(e) lists every problem with its path."""


class RenderError(RuntimeError):
    """A scene failed while drawing. Names the scene and time."""


class Project:
    def __init__(self, spec, base_dir=".", fmt=None, root=None, allow_abs=False, plugins=(), blur=None, autotime_vo=None):
        paths.configure(root or base_dir, allow_abs)
        load_builtin(); load_plugins(list(plugins))
        errs = validate(spec)
        if errs: raise SpecError("spec has %d problem(s):\n  - " % len(errs) + "\n  - ".join(errs))
        self.spec = copy.deepcopy(spec); self.base_dir = base_dir
        self.fmt = get_format(fmt or spec.get("format", "reel")); self.theme = load_theme(spec.get("theme"), base_dir)
        self.fps = int(spec.get("fps", FPS)); self.blur = max(1, int(blur if blur is not None else spec.get("blur", 1)))
        self.post_cfg = {**LOOKS.get(spec.get("look", "clean"), {}), **(spec.get("post") or {})}
        if self.theme.grain and "grain" not in self.post_cfg: self.post_cfg["grain"] = self.theme.grain
        self.auto_cam = MOTION.get(spec.get("motion", "calm"))
        self.warnings = []
        self.voiceover = paths.resolve(spec["voiceover"], "voiceover") if spec.get("voiceover") else None
        self.music = self._music(spec)
        scenes = self.spec["scenes"]
        self.word_times = None; self.voice_segments = None
        sidecar = (self.voiceover + ".timing.json") if self.voiceover else None
        if spec.get("align") and sidecar and os.path.exists(sidecar):
            with open(sidecar, encoding="utf-8") as fh: self._voice_led(scenes, json.load(fh))
        elif spec.get("align") and self.voiceover:
            ws = [str(sc.get("say", "")).split() for sc in scenes]; flat = [w for x in ws for w in x]
            if flat:
                self.word_times = align_mod.align(self.voiceover, flat); idx, t_prev = 0, 0.0
                for sc, w in zip(scenes, ws):
                    if w:
                        idx += len(w); sc["dur"] = round(max(1.2, self.word_times[idx - 1]["t1"] + 0.4 - t_prev), 2)
                    t_prev += sc["dur"]
                scenes[-1]["dur"] = round(scenes[-1]["dur"] + 0.5, 2)
        elif (spec.get("autotime") or autotime_vo) and self.voiceover:
            for sc, d in zip(scenes, autotime.durations(self.voiceover, len(scenes))): sc["dur"] = d
        if self.word_times is not None and self.voice_segments is None: self._inject_words(scenes)
        if self.music and isinstance(self.music, dict) and "mood" in self.music and self.voiceover is None and spec.get("beat_sync", True):
            self._beat_snap(scenes)
        self.timeline, t = [], 0.0
        for sc in scenes: self.timeline.append((t, t + sc["dur"], sc)); t += sc["dur"]
        self.punches = self._punches() if spec.get("punch", True) else []
        self.duration = t; self.n_frames = int(math.ceil(t * self.fps))
        if self.voiceover:
            vd = audio.probe_duration(self.voiceover)
            if vd > t + 0.05: self.warnings.append(f"voiceover is {vd:.1f}s but scenes total {t:.1f}s: the end will be cut. Use \"autotime\": true or lengthen scenes.")
        for i, sc in enumerate(scenes):
            if sc["type"] == "code":
                need = sum(len(str(x)) for x in sc.get("lines", [])) / max(1.0, float(sc.get("cps", 38))) + 0.4
                if need > sc["dur"]: self.warnings.append(f"scenes[{i}] (code): typing needs {need:.1f}s but the scene lasts {sc['dur']}s; raise cps or dur")
        # captions come from `say` only when there is narration (or you ask with "say_captions": true); otherwise they would repeat the on-screen text
        caption_scenes = scenes if (self.voiceover or spec.get("say_captions")) else [{k: v for k, v in sc.items() if k != "say"} for sc in scenes]
        self.captions = captions_mod.build(caption_scenes, spec.get("captions"), word_times=self.word_times)
        self.karaoke = spec.get("captions_style") == "karaoke"

    def _voice_led(self, scenes, data):
        """Use exact per-scene narration timing from the sidecar written by `motionspec voice`."""
        by_scene = {e["scene"]: e for e in data["scenes"]}; t, segs, flat = 0.0, [], []
        for i, sc in enumerate(scenes):
            e = by_scene.get(i)
            if e:
                lead = 0.2; sc["dur"] = round(max(sc["dur"], e["t1"] - e["t0"] + lead + 0.45), 2); segs.append((e["t0"], e["t1"], t + lead))
                words = [{"word": w["word"], "t0": round(w["t0"] - e["t0"] + lead, 3), "t1": round(w["t1"] - e["t0"] + lead, 3)} for w in e["words"]]
                sc["_words"] = words; flat += [{"word": w["word"], "t0": round(t + w["t0"], 3), "t1": round(t + w["t1"], 3)} for w in words]
            t += sc["dur"]
        self.voice_segments = segs; self.word_times = flat

    def _inject_words(self, scenes):
        """Give each scene its spoken words (times relative to the scene start) so scenes can sync to them."""
        t, i = 0.0, 0
        for sc in scenes:
            n = len(str(sc.get("say", "")).split())
            if n and self.word_times and i + n <= len(self.word_times):
                sc["_words"] = [{"word": w["word"], "t0": round(w["t0"] - t, 3), "t1": round(w["t1"] - t, 3)} for w in self.word_times[i:i + n]]
            i += n; t += sc["dur"]

    def _beat_snap(self, scenes):
        """Land every cut on the music's beat: scene ends snap to the nearest beat (at least two beats per scene)."""
        from .music import MOODS
        beat = 60.0 / MOODS[self.music["mood"]]["bpm"]; cum = 0.0
        for sc in scenes:
            end = max(cum + 2 * beat, round((cum + sc["dur"]) / beat) * beat); sc["dur"] = round(end - cum, 3); cum = end

    def _punches(self):
        """Absolute times that get a camera push: every scene start after the first, plus impact-type sound cues."""
        pts = [a for a, _, _ in self.timeline[1:]]
        for a, _, sc in self.timeline:
            pts += [a + ct for ct, name, *_ in REGISTRY[sc["type"]]["cues"](sc) if name in ("impact", "stamp", "thud")]
        return sorted(pts)

    @staticmethod
    def _music(spec):
        """Background music: "auto" (default) composes an original track for the video's kind; "off" disables; a path uses your file;
        {"mood": "warm", "db": -6} picks the mood; {"src": "bed.mp3", "db": -22} uses a file."""
        from . import music as music_mod
        m = spec.get("music", "auto")
        if m in ("off", False, None): return None
        seed = spec.get("id", "motionspec")
        if m == "auto": return {"mood": music_mod.mood_for(spec.get("kind", "general")), "seed": seed}
        if isinstance(m, str): return paths.resolve(m, "music")
        if "mood" in m: return {"seed": seed, **m}
        return {**m, "src": paths.resolve(m["src"], "music.src")}

    # ---- drawing
    def _scene_canvas(self, idx, local_t, warns):
        a, b, sc = self.timeline[idx]
        th = self.theme
        if sc.get("invert"):                                    # palette flip: light-on-dark becomes dark-on-light for one scene
            nb, nf = th.fg, th.bg
            th = dataclasses.replace(th, bg=nb, fg=nf, muted=mix(nf, nb, 0.4), dim=mix(nb, nf, 0.14), card=mix(nb, nf, 0.07), backdrop="none")
        c = Canvas(self.fmt, th, sc.get("bg"), sc.get("gradient"), warns)
        try:
            if not sc.get("bg") or sc.get("backdrop"):
                backdrop.draw(c, a + local_t, sc.get("backdrop", self.spec.get("backdrop", self.theme.backdrop)))
            REGISTRY[sc["type"]]["draw"](c, local_t, sc)
        except Exception as e:                                  # name the scene; do not hide the cause
            raise RenderError(f"scenes[{idx}] ({sc['type']}) at {a + local_t:.2f}s: {type(e).__name__}: {e}") from e
        cam = sc.get("camera", self.auto_cam if sc["type"] not in ("slam", "image", "clip") else None)
        return apply_camera(c.img, cam, local_t, sc["dur"])

    def _caption(self, img, t):
        for cap in self.captions:
            if cap["t0"] <= t < cap["t1"]:
                a = min(prog(t, cap["t0"], 0.15), 1 - prog(t, cap["t1"] - 0.15, 0.15) if cap["t1"] - t < 0.15 else 1)
                c = Canvas.__new__(Canvas); c.fmt, c.theme, c.W, c.H, c.u, c.wide, c.tall, c.img, c.warnings = self.fmt, self.theme, self.fmt.W, self.fmt.H, self.fmt.u, self.fmt.wide, self.fmt.tall, img, []
                txt = c.wrap(cap["text"], "bold", c.S(50), self.fmt.W * 0.78); n = txt.count("\n") + 1
                y = self.fmt.H * (0.73 if self.fmt.tall else 0.82)
                c.rect((self.fmt.W * 0.06, y, self.fmt.W * 0.94, y + c.S(40) + n * c.S(62)), "bg", 0.78 * a, radius=c.S(26))
                c.text(self.fmt.W / 2, y + c.S(20), txt, "bold", 50, "fg", a, spacing=12)

    def frame_at(self, t, index, warns=None):
        warns = warns if warns is not None else self.warnings
        t = min(max(t, 0.0), self.duration - 1e-6)
        k = next(i for i, (a, b, _) in enumerate(self.timeline) if a <= t < b)
        a, b, sc = self.timeline[k]; img = self._scene_canvas(k, t - a, warns)
        nxt = self.timeline[k + 1][2] if k + 1 < len(self.timeline) else None
        kind = nxt.get("transition", self.spec.get("transition", "fade")) if nxt else None
        xf = 0.0 if (nxt is None or kind == "cut") else min(0.55 if kind in ("push", "wipe", "zoom") else XF, sc["dur"] * 0.4, nxt["dur"] * 0.4)
        if xf and b - t < xf:
            other = self._scene_canvas(k + 1, xf - (b - t), warns)
            if kind in ("push", "wipe", "zoom"):          # blur the movement itself: both scenes are drawn once, the move is averaged over the shutter
                shutter = 0.5 / self.fps
                img = average([_transition(img, other, in_out(max(0.0, min(1.0, 1 - (b - (t + ((j + 0.5) / 12 - 0.5) * shutter)) / xf))), kind) for j in range(12)])
            else:
                img = _transition(img, other, in_out(1 - (b - t) / xf), kind)
        img = apply_punch(img, t, self.punches)
        self._caption(img, t)
        return post(img, self.post_cfg, index)

    def frame(self, index, warns=None):
        t0 = index / self.fps; n = self.blur
        if n <= 1: return self.frame_at(t0, index, warns)
        shutter = 0.5 / self.fps                                 # 180-degree shutter
        return average([self.frame_at(t0 + ((k + 0.5) / n - 0.5) * shutter, index, warns) for k in range(n)])

    def cues(self):
        out = []
        for a, _, sc in self.timeline:
            out += [(a + c[0], c[1], *c[2:]) for c in REGISTRY[sc["type"]]["cues"](sc)]       # (time, sound[, gain_db])
        out += [(c["t"], c["sound"]) for c in self.spec.get("cues", [])]      # manual cue sheet: [{"t": 1.2, "sound": "impact"}]
        dens = self.spec.get("sfx_density", "rich")
        if dens == "off": return []
        if dens == "light": out = [c for c in out if c[1] not in ("tick", "key", "click")]
        else:                                                                    # rich: a sound under every cut
            for k, (a, b, sc) in enumerate(self.timeline[:-1]):
                nxt = self.timeline[k + 1][2]; kind = nxt.get("transition", self.spec.get("transition", "fade"))
                if kind != "cut": out.append((b - 0.12, "whoosh" if kind in ("push", "wipe", "zoom") else "swish", -7))
        return sorted(out, key=lambda c: c[0])


def _transition(a, b, k, kind):
    """Blend scene image `a` into `b` at progress k in [0,1]. kinds: fade | push | wipe | zoom."""
    W, H = a.size
    if kind == "push":                                   # the new scene pushes the old one up and out
        out = Image.new("RGB", (W, H)); off = int(H * k); out.paste(a, (0, -off)); out.paste(b, (0, H - off)); return out
    if kind == "wipe":                                   # a soft vertical edge sweeps left to right
        x = int(W * k); edge = max(4, int(W * 0.05)); out = a.copy()
        if x > 0: out.paste(b.crop((0, 0, x, H)), (0, 0))
        w = min(edge, W - x)
        if w > 0:
            ramp = Image.linear_gradient("L").rotate(90).transpose(Image.FLIP_LEFT_RIGHT).resize((edge, H)).crop((0, 0, w, H))
            out.paste(Image.composite(b.crop((x, 0, x + w, H)), a.crop((x, 0, x + w, H)), ramp), (x, 0))
        return out
    if kind == "zoom":                                   # the old scene pushes in while it fades out
        z = 1 + 0.18 * k; cw, ch = W / z, H / z
        return Image.blend(a.resize((W, H), Image.BICUBIC, box=((W - cw) / 2, (H - ch) / 2, (W + cw) / 2, (H + ch) / 2)), b, k)
    return Image.blend(a, b, k)


def load_spec(path):
    try:
        with open(path, encoding="utf-8") as f: return json.load(f)
    except json.JSONDecodeError as e:
        raise SpecError(f"{path}: invalid JSON at line {e.lineno} column {e.colno}: {e.msg}") from None
    except OSError as e:
        raise SpecError(f"cannot read spec '{path}': {e.strerror}") from None


# ------------------------------------------------------------------ parallel rendering
_P = None


def _init(spec_path, kw):
    global _P
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    _P = Project(load_spec(spec_path), os.path.dirname(os.path.abspath(spec_path)), **kw)


def _work(i):
    w = []; return i, _P.frame(i, w).tobytes(), w


def render_video(spec_path, out, fmt=None, jobs=None, crf=18, blur=None, sfx=True, plugins=(), root=None, allow_abs=False, quiet=False, music=True):
    spec_path = os.path.abspath(spec_path); kw = dict(fmt=fmt, blur=blur, plugins=tuple(plugins), root=root, allow_abs=allow_abs)
    P = Project(load_spec(spec_path), os.path.dirname(spec_path), **kw)
    os.makedirs(os.path.dirname(os.path.abspath(out)) or ".", exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="motionspec_"); wav = None
    cues = P.cues() if sfx and P.spec.get("sfx", True) else []
    bed = P.music if music else None
    if cues or P.voiceover or bed: wav = audio.mix(cues, P.duration, os.path.join(tmp, "mix.wav"), P.voiceover, bed, voice_segments=P.voice_segments)
    f = P.fmt
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{f.W}x{f.H}", "-r", str(P.fps), "-i", "-"]
    if wav: cmd += ["-i", wav]
    cmd += ["-vf", "format=yuv420p", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-c:v", "libx264", "-preset", "medium",
            "-crf", str(crf), "-movflags", "+faststart", "-t", f"{P.duration:.3f}"]
    if wav: cmd += ["-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", "48000", "-c:a", "aac", "-b:a", "192k"]
    try: ff = subprocess.Popen(cmd + [out], stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    except FileNotFoundError: raise RenderError("ffmpeg not found on PATH. Install it and run `motionspec doctor`.") from None
    err = []; threading.Thread(target=lambda: err.append(ff.stderr.read().decode(errors="ignore")), daemon=True).start()
    n = P.n_frames; jobs = jobs or default_jobs(); seen = set(P.warnings); t0 = time.time()
    try:
        if jobs == 1:
            for i in range(n):
                w = []; ff.stdin.write(P.frame(i, w).tobytes()); seen.update(w); _progress(i + 1, n, t0, quiet)
        else:
            ctx = mp.get_context("spawn")
            with ctx.Pool(jobs, _init, (spec_path, kw)) as pool:
                for i, data, w in pool.imap(_work, range(n), chunksize=4):
                    ff.stdin.write(data); seen.update(w); _progress(i + 1, n, t0, quiet)
        ff.stdin.close()
    except BrokenPipeError:
        ff.wait(); raise RenderError("ffmpeg stopped early:\n" + (err[0] if err else "")) from None
    except BaseException:
        ff.kill(); raise
    rc = ff.wait()
    if rc: raise RenderError("ffmpeg failed:\n" + (err[0] if err else ""))
    if not quiet: print(f"\n{out}  [{f.name} {f.W}x{f.H}, {P.duration:.1f}s, {n} frames, {time.time() - t0:.0f}s on {jobs} process(es)]")
    return sorted(seen)


def default_jobs():
    """Worker processes: cores - 1, capped at 10 and by free memory (about 0.7 GB each), so a render never starves the machine."""
    jobs = max(1, min((os.cpu_count() or 2) - 1, 10))
    try:
        import ctypes
        class MS(ctypes.Structure):
            _fields_ = [("l", ctypes.c_ulong), ("load", ctypes.c_ulong), ("tp", ctypes.c_ulonglong), ("ap", ctypes.c_ulonglong), ("tv", ctypes.c_ulonglong), ("av", ctypes.c_ulonglong), ("tvv", ctypes.c_ulonglong), ("avv", ctypes.c_ulonglong), ("x", ctypes.c_ulonglong)]
        m = MS(); m.l = ctypes.sizeof(MS)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)): jobs = max(1, min(jobs, int(m.ap / 2 ** 30 / 0.7)))
    except (AttributeError, OSError, ImportError):
        try:
            with open("/proc/meminfo") as f: kb = int(next(l for l in f if l.startswith("MemAvailable")).split()[1]); jobs = max(1, min(jobs, int(kb / 2 ** 20 / 0.7)))
        except (OSError, StopIteration, ValueError): pass
    return jobs


def _progress(i, n, t0, quiet):
    if quiet or (i % 30 and i != n): return
    el = time.time() - t0; eta = el / i * (n - i)
    print(f"\r  frame {i}/{n}  {i / el:.1f} fps  eta {eta:.0f}s ", end="", file=sys.stderr, flush=True)


def stills(spec_path, times, out_dir, fmt=None, plugins=(), root=None, allow_abs=False):
    spec_path = os.path.abspath(spec_path)
    P = Project(load_spec(spec_path), os.path.dirname(spec_path), fmt=fmt, plugins=plugins, root=root, allow_abs=allow_abs)
    os.makedirs(out_dir, exist_ok=True); out = []
    for t in times:
        p = os.path.join(out_dir, f"{os.path.splitext(os.path.basename(spec_path))[0]}_{P.fmt.name}_{t:06.2f}.png")
        P.frame_at(float(t), int(t * P.fps)).save(p); out.append(p)
    return out, P.warnings


def contact_sheet(spec_path, out_png, fmt=None, plugins=(), root=None, allow_abs=False, cols=None):
    """One still per scene (taken when the scene has settled) on a labelled grid: the fast way to review a spec."""
    spec_path = os.path.abspath(spec_path)
    P = Project(load_spec(spec_path), os.path.dirname(spec_path), fmt=fmt, plugins=plugins, root=root, allow_abs=allow_abs)
    thumbs = []
    for a, b, sc in P.timeline:
        t = a + min(sc["dur"] * 0.7, sc["dur"] - 0.05); im = P.frame_at(t, int(t * P.fps)); th = 360 / max(im.width, im.height) * (1.0 if im.width >= im.height else 1.0)
        thumbs.append((im.resize((max(1, int(im.width * th * (2.2 if im.width > im.height else 1.0))), max(1, int(im.height * th * (2.2 if im.width > im.height else 1.0)))), Image.LANCZOS), sc))
    tw, thh = max(t.width for t, _ in thumbs), max(t.height for t, _ in thumbs); cols = cols or min(len(thumbs), 4 if thw_ok(tw) else 3)
    rows = -(-len(thumbs) // cols); pad = 16; lab = 28
    sheet = Image.new("RGB", (cols * (tw + pad) + pad, rows * (thh + lab + pad) + pad), (30, 30, 34)); d = ImageDraw.Draw(sheet)
    for i, (im, sc) in enumerate(thumbs):
        x = pad + (i % cols) * (tw + pad); y = pad + (i // cols) * (thh + lab + pad)
        sheet.paste(im, (x, y + lab)); d.text((x, y + 6), f"{i + 1}. {sc['type']}  {sc['dur']}s", fill=(220, 220, 225))
    os.makedirs(os.path.dirname(os.path.abspath(out_png)) or ".", exist_ok=True); sheet.save(out_png); return out_png, P.warnings


def thw_ok(w): return w < 500
