"""Project loading and rendering. A Project turns a validated spec into frames; render_video fans frames out across
processes (they are independent, so the speed-up is close to linear) and streams them in order into one ffmpeg process."""
import copy
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

from . import audio, autotime, captions as captions_mod, paths
from .canvas import Canvas
from .constants import FPS
from .ease import in_out, prog
from .layout import get_format
from .post import apply_camera, average, post
from .scenes import REGISTRY, load_builtin, load_plugins
from .theme import load_theme
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
        self.post_cfg = spec.get("post") or ({"grain": self.theme.grain} if self.theme.grain else {})
        self.warnings = []
        self.voiceover = paths.resolve(spec["voiceover"], "voiceover") if spec.get("voiceover") else None
        self.music = spec.get("music")
        if isinstance(self.music, str): self.music = paths.resolve(self.music, "music")
        elif isinstance(self.music, dict): self.music = {**self.music, "src": paths.resolve(self.music["src"], "music.src")}
        scenes = self.spec["scenes"]
        if (spec.get("autotime") or autotime_vo) and self.voiceover:
            for sc, d in zip(scenes, autotime.durations(self.voiceover, len(scenes))): sc["dur"] = d
        self.timeline, t = [], 0.0
        for sc in scenes: self.timeline.append((t, t + sc["dur"], sc)); t += sc["dur"]
        self.duration = t; self.n_frames = int(math.ceil(t * self.fps))
        if self.voiceover:
            vd = audio.probe_duration(self.voiceover)
            if vd > t + 0.05: self.warnings.append(f"voiceover is {vd:.1f}s but scenes total {t:.1f}s: the end will be cut. Use \"autotime\": true or lengthen scenes.")
        self.captions = captions_mod.build(scenes, spec.get("captions"))

    # ---- drawing
    def _scene_canvas(self, idx, local_t, warns):
        a, b, sc = self.timeline[idx]
        c = Canvas(self.fmt, self.theme, sc.get("bg"), sc.get("gradient"), warns)
        try: REGISTRY[sc["type"]]["draw"](c, local_t, sc)
        except Exception as e:                                  # name the scene; do not hide the cause
            raise RenderError(f"scenes[{idx}] ({sc['type']}) at {a + local_t:.2f}s: {type(e).__name__}: {e}") from e
        return apply_camera(c.img, sc.get("camera"), local_t, sc["dur"])

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
        xf = 0.0 if (nxt is None or nxt.get("transition") == "cut") else min(XF, sc["dur"] * 0.4, nxt["dur"] * 0.4)
        if xf and b - t < xf:
            img = Image.blend(img, self._scene_canvas(k + 1, xf - (b - t), warns), in_out(1 - (b - t) / xf))
        self._caption(img, t)
        return post(img, self.post_cfg, index)

    def frame(self, index, warns=None):
        t0 = index / self.fps
        if self.blur <= 1: return self.frame_at(t0, index, warns)
        shutter = 0.5 / self.fps                                 # 180-degree shutter
        return average([self.frame_at(t0 + ((k + 0.5) / self.blur - 0.5) * shutter, index, warns) for k in range(self.blur)])

    def cues(self):
        out = []
        for a, _, sc in self.timeline:
            out += [(a + ct, name) for ct, name in REGISTRY[sc["type"]]["cues"](sc)]
        return out


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


def render_video(spec_path, out, fmt=None, jobs=None, crf=18, blur=None, sfx=True, plugins=(), root=None, allow_abs=False, quiet=False):
    spec_path = os.path.abspath(spec_path); kw = dict(fmt=fmt, blur=blur, plugins=tuple(plugins), root=root, allow_abs=allow_abs)
    P = Project(load_spec(spec_path), os.path.dirname(spec_path), **kw)
    os.makedirs(os.path.dirname(os.path.abspath(out)) or ".", exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="motionspec_"); wav = None
    cues = P.cues() if sfx and P.spec.get("sfx", True) else []
    if cues or P.voiceover or P.music: wav = audio.mix(cues, P.duration, os.path.join(tmp, "mix.wav"), P.voiceover, P.music)
    f = P.fmt
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{f.W}x{f.H}", "-r", str(P.fps), "-i", "-"]
    if wav: cmd += ["-i", wav]
    cmd += ["-vf", "format=yuv420p", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-c:v", "libx264", "-preset", "medium",
            "-crf", str(crf), "-movflags", "+faststart", "-t", f"{P.duration:.3f}"]
    if wav: cmd += ["-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", "48000", "-c:a", "aac", "-b:a", "192k"]
    try: ff = subprocess.Popen(cmd + [out], stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    except FileNotFoundError: raise RenderError("ffmpeg not found on PATH. Install it and run `motionspec doctor`.") from None
    err = []; threading.Thread(target=lambda: err.append(ff.stderr.read().decode(errors="ignore")), daemon=True).start()
    n = P.n_frames; jobs = jobs or max(1, (os.cpu_count() or 2) - 1); seen = set(P.warnings); t0 = time.time()
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
