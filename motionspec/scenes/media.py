"""Media scenes: image (Ken Burns), clip (video), code (typewriter). Every path goes through the sandbox in `paths`."""
import hashlib
import os
import shutil
import subprocess
import tempfile
from functools import lru_cache

from PIL import Image

from .. import paths
from ..constants import FPS
from ..ease import in_out, lerp, out_cubic, prog
from . import scene


@lru_cache(maxsize=6)
def _open(path):
    return Image.open(path).convert("RGB")


def _cover(im, bw, bh, zoom, px=0.5, py=0.5):
    """Crop-and-scale `im` to fill bw x bh at a given zoom, with a float (sub-pixel) crop box so slow pushes stay smooth."""
    k = max(bw / im.width, bh / im.height) * zoom
    cw, ch = bw / k, bh / k
    l = (im.width - cw) * px; tp = (im.height - ch) * py
    return im.resize((bw, bh), Image.BICUBIC, box=(l, tp, l + cw, tp + ch))


def _frame_box(c, full):
    return (c.W, c.H) if full else (int(c.W * 0.9), int(c.H * (0.62 if not c.wide else 0.78)))


@scene("image", fields={"src": (str, True), "caption": (str, False), "zoom": ((int, float), False), "zoom_dur": ((int, float), False),
                        "pan": (list, False), "fit": (str, False)},
       cues=lambda s: [(0.05, "whoosh"), (0.5, "pop", -9)],
       desc="Screenshot or photo with a slow zoom (Ken Burns). `pan` [x0,y0,x1,y1] in 0..1 moves the crop; `fit`: card (default) | full.")
def image(c, t, s):
    src = _open(paths.resolve(s["src"], "image.src"))
    full = s.get("fit") == "full"; bw, bh = _frame_box(c, full)
    k = in_out(prog(t, 0, s.get("zoom_dur", 6.0))); z = lerp(1.0, s.get("zoom", 1.1), k)
    pan = s.get("pan", [0.5, 0.5, 0.5, 0.5])
    crop = _cover(src, bw, bh, z, lerp(pan[0], pan[2], k), lerp(pan[1], pan[3], k))
    c.paste_image(crop, (c.W - bw) / 2, 0 if full else c.H * (0.12 if not c.wide else 0.07), out_cubic(prog(t, 0.05, .5)), 0 if full else c.S(28))
    _caption(c, s, t, full)


def _caption(c, s, t, full):
    if not s.get("caption"): return
    if full: c.rect((0, c.H * 0.76, c.W, c.H), "bg", 0.6 * prog(t, 0.5, .4))
    c.text(c.cx, c.H * (0.82 if not c.wide else 0.89), c.fit(s["caption"], "bold", 50), "bold", 50, "fg", prog(t, 0.6, .5), shadow=1)


def extract_clip(path, start, dur, w, h):
    """Decode a clip to lossless PNG frames once; returns (dir, count). Atomic: parallel workers never see a half-written dir."""
    key = hashlib.sha1(f"{path}|{os.path.getmtime(path)}|{start}|{dur}|{FPS}|{w}x{h}".encode()).hexdigest()[:16]
    d = os.path.join(tempfile.gettempdir(), "motionspec_clips", key)
    if not os.path.isdir(d):
        tmp = d + f".tmp{os.getpid()}"; os.makedirs(tmp, exist_ok=True)
        vf = f"fps={FPS},scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}"
        try:
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-protocol_whitelist", "file", "-ss", str(float(start)), "-t", str(float(dur)),
                            "-i", path, "-vf", vf, os.path.join(tmp, "f%05d.png")], check=True, timeout=600, capture_output=True)
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
            shutil.rmtree(tmp, ignore_errors=True)
            raise paths.PathError(f"could not decode clip '{path}' with ffmpeg ({getattr(e, 'stderr', b'').decode(errors='ignore')[:200] or e}). Run `motionspec doctor`.") from None
        try: os.rename(tmp, d)
        except OSError: shutil.rmtree(tmp, ignore_errors=True)      # another worker won the race: use theirs
    n = len([f for f in os.listdir(d) if f.endswith(".png")])
    if n == 0: raise paths.PathError(f"clip '{path}' produced no frames (check start/duration)")
    return d, n


@scene("clip", fields={"src": (str, True), "start": ((int, float), False), "caption": (str, False), "loop": (bool, False), "fit": (str, False)},
       cues=lambda s: [], desc="Video clip (screen recording, b-roll), muted. Plays from `start`; `loop` repeats. Sound comes from the voiceover.")
def clip(c, t, s):
    full = s.get("fit") == "full"; bw, bh = _frame_box(c, full)
    d, n = extract_clip(paths.resolve(s["src"], "clip.src"), s.get("start", 0), s["dur"], bw, bh)
    i = int(t * FPS); i = i % n if s.get("loop") else min(i, n - 1)
    with Image.open(os.path.join(d, f"f{i + 1:05d}.png")) as im: im.load(); frame = im.copy()
    c.paste_image(frame, (c.W - bw) / 2, 0 if full else c.H * (0.12 if not c.wide else 0.07), out_cubic(prog(t, 0, .3)), 0 if full else c.S(28))
    _caption(c, s, t, full)


@scene("code", fields={"title": (str, False), "lines": (list, True), "cps": ((int, float), False), "highlight": (list, False)},
       cues=lambda s: [(0.4 + k * 0.09, "key") for k in range(min(40, sum(len(str(x)) for x in s.get("lines", [])) // 2))], desc="Typewriter code or terminal block. `lines`, characters/second `cps`, `highlight` line numbers (1-based).")
def code(c, t, s):
    lines = [str(x) for x in s["lines"]]
    if not lines: return
    cps = max(1.0, float(s.get("cps", 38))); chars = int(max(0, t - 0.4) * cps)      # cps: characters per second; pick it so typing ends before the scene does
    x0, x1 = c.W * 0.06, c.W * 0.94; size = 34; lh = c.S(size * 1.55)
    h = lh * len(lines) + c.S(150); y0 = c.H / 2 - h / 2
    if s.get("title"): c.text(c.cx, y0 - c.S(110), c.fit(s["title"], "bold", 56, 0.86), "bold", 56, "fg", prog(t, 0.1, .4))
    c.shadow_rect((x0, y0, x1, y0 + h), c.S(26), c.S(30), 0.5, c.S(16)); c.rect((x0, y0, x1, y0 + h), "card", radius=c.S(26))
    for k, col in enumerate(("negative", "accent", "positive")): c.dot(x0 + c.S(40 + k * 36), y0 + c.S(42), c.S(10), col)
    hl = set(s.get("highlight", [])); y = y0 + c.S(90); left = chars; max_w = x1 - x0 - c.S(80)
    for i, ln in enumerate(lines):
        shown = ln[: max(0, left)]; typing = 0 <= left < len(ln) or (left == len(ln) and i == len(lines) - 1)
        left -= len(ln)
        if (i + 1) in hl: c.rect((x0 + c.S(14), y - c.S(6), x1 - c.S(14), y + lh - c.S(8)), "dim", 0.9, radius=c.S(8))
        c.text(x0 + c.S(40), y, shown, "mono", size, "accent" if (i + 1) in hl else "fg", 1, anchor="la")
        if typing and int(t * 2) % 2 == 0:
            w = c.text_size(shown, "mono", size)[0] if shown else 0
            c.rect((x0 + c.S(40) + min(w, max_w) + c.S(4), y + c.S(4), x0 + c.S(40) + min(w, max_w) + c.S(22), y + lh - c.S(10)), "accent")
        y += lh
        if left < 0: break


@scene("device", fields={"src": (str, True), "kind": (str, False), "url": (str, False), "caption": (str, False),
                         "zoom": ((int, float), False), "pan": (list, False)},
       cues=lambda s: [(0.05, "swish"), (0.6, "click"), (0.75, "pop", -9)],
       desc="Screenshot inside a browser window (`kind`: browser, default on wide) or phone (`kind`: phone, default on tall) frame, with a slow push-in.")
def device(c, t, s):
    src = _open(paths.resolve(s["src"], "device.src")); kind = s.get("kind", "browser" if c.wide else "phone")
    p = out_cubic(prog(t, 0.05, 0.7)); k = in_out(prog(t, 0, 6.0)); z = lerp(1.0, s.get("zoom", 1.06), k); pan = s.get("pan", [0.5, 0.3, 0.5, 0.5])
    if kind == "phone":
        h = c.H * 0.66; w = h * 0.49; x0 = c.cx - w / 2; y0 = c.H * 0.1 + (1 - p) * c.S(80)
        c.shadow_rect((x0 - c.S(14), y0 - c.S(14), x0 + w + c.S(14), y0 + h + c.S(14)), c.S(70), c.S(40), 0.6 * p, c.S(22))
        c.rect((x0 - c.S(14), y0 - c.S(14), x0 + w + c.S(14), y0 + h + c.S(14)), "card", p, radius=c.S(70))
        c.rect((x0 - c.S(14), y0 - c.S(14), x0 + w + c.S(14), y0 + h + c.S(14)), "dim", p * 0.5, radius=c.S(70))
        crop = _cover(src, int(w), int(h), z, lerp(pan[0], pan[2], k), lerp(pan[1], pan[3], k))
        c.paste_image(crop, x0, y0, p, c.S(56)); c.rect((c.cx - c.S(70), y0 + c.S(14), c.cx + c.S(70), y0 + c.S(40)), "card", p, radius=c.S(14))
    else:
        w = c.W * (0.8 if c.wide else 0.9); bar = c.S(70); h = c.H * (0.72 if c.wide else 0.5); x0 = c.cx - w / 2; y0 = c.H * (0.1 if c.wide else 0.16) + (1 - p) * c.S(70)
        c.shadow_rect((x0, y0, x0 + w, y0 + bar + h), c.S(26), c.S(34), 0.55 * p, c.S(18)); c.rect((x0, y0, x0 + w, y0 + bar + h), "card", p, radius=c.S(26))
        for i, col in enumerate(("negative", "accent", "positive")): c.dot(x0 + c.S(40 + i * 34), y0 + bar / 2, c.S(9), col, p)
        c.rect((x0 + c.S(180), y0 + bar * 0.2, x0 + w - c.S(40), y0 + bar * 0.8), "dim", p, radius=c.S(14))
        if s.get("url"): c.text(x0 + c.S(210), y0 + bar * 0.28, s["url"], "mono", 26, "muted", p, anchor="la")
        crop = _cover(src, int(w), int(h), z, lerp(pan[0], pan[2], k), lerp(pan[1], pan[3], k)); c.paste_image(crop, x0, y0 + bar, p, 0)
        c.rect((x0, y0 + bar + h - c.S(26), x0 + w, y0 + bar + h), "card", p, radius=c.S(26))
    if s.get("caption"): c.text(c.cx, c.H * (0.9 if c.wide else 0.82), c.fit(s["caption"], "bold", 50, 0.8), "bold", 50, "fg", prog(t, 0.6, .5), shadow=1)
