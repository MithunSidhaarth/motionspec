"""Per-scene camera and per-frame post effects. All deterministic: the same (spec, frame index) always gives the same pixels.
Effects use Pillow's C-level image operations and work at low resolution where the result is blurry anyway, so they stay cheap."""
from functools import lru_cache

import numpy as np
from PIL import Image, ImageChops, ImageFilter

from .ease import drift, in_out, lerp, prog


def apply_camera(img, cam, t, dur):
    """cam: {"zoom": [from, to], "pan": [dx0, dy0, dx1, dy1] (fractions of the frame), "drift": 0..1 handheld wobble}.
    A sub-pixel crop-and-resize of the finished scene, so every scene gets a camera for free."""
    if not cam: return img
    W, H = img.size; k = in_out(prog(t, 0, dur)); z0, z1 = cam.get("zoom", [1.0, 1.0])
    z = max(1.0, lerp(z0, z1, k)); pan = cam.get("pan", [0, 0, 0, 0]); w = float(cam.get("drift", 0.0))
    dx = lerp(pan[0], pan[2], k) * W + w * 0.012 * W * drift(t, 1.3); dy = lerp(pan[1], pan[3], k) * H + w * 0.012 * H * drift(t, 4.1)
    cw, ch = W / z, H / z
    l = min(max((W - cw) / 2 + dx, 0), W - cw); tp = min(max((H - ch) / 2 + dy, 0), H - ch)
    return img.resize((W, H), Image.BICUBIC, box=(l, tp, l + cw, tp + ch))


@lru_cache(maxsize=4)
def _grain_tiles(W, H, n=8):
    """Eight grain frames as 8-bit images centred on 128 (cycled by frame index)."""
    rng = np.random.default_rng(11)
    return [Image.fromarray(np.clip(128 + rng.normal(0, 38, (H, W)), 0, 255).astype(np.uint8), "L").convert("RGB") for _ in range(n)]


@lru_cache(maxsize=48)
def _grain(W, H, strength, idx):
    """Grain frame `idx` scaled to `strength`, cached so each frame only pays for one add."""
    tile = _grain_tiles(W, H)[idx]
    return tile if strength >= 1 else Image.blend(Image.new("RGB", tile.size, (128, 128, 128)), tile, strength)


@lru_cache(maxsize=64)
def _lut(kind, strength):
    if kind == "thresh": return [min(255, max(0, int((v - 165) * 3.2))) for v in range(256)]
    return [min(255, int(v * strength)) for v in range(256)]


def _is_bright(img):
    """True when the frame is mostly light (mean luminance above about 55%)."""
    from PIL import ImageStat
    return ImageStat.Stat(img.reduce(16).convert("L")).mean[0] > 140


@lru_cache(maxsize=8)
def _tone(amount):
    """A gentle S-curve with a soft highlight shoulder: more contrast in the mids, highlights roll off instead of clipping."""
    out = []
    for v in range(256):
        x = v / 255; s = x * x * (3 - 2 * x); y = (1 - amount) * x + amount * s
        out.append(int(round(255 * min(1.0, y * 0.985 + 0.012))))
    return out


def post(img, cfg, frame_index):
    """cfg: {"bloom": 0..1, "halation": 0..1, "tone": bool, "grain": 0..1, "aberration": px}.
    Returns a new PIL image (or the same one when nothing is enabled)."""
    if not cfg: return img
    bloom, grain, ab = cfg.get("bloom", 0), cfg.get("grain", 0), cfg.get("aberration", 0)
    hal, tone = cfg.get("halation", 0), cfg.get("tone", False)
    if not (bloom or grain or ab or hal or tone): return img
    if tone: img = img.point(_tone(0.35) * 3)
    if (bloom or hal) and _is_bright(img): bloom = hal = 0          # glow looks muddy on a mostly white frame: skip it
    if hal:                                           # warm red-orange glow bleeding from the brightest areas, like light in film
        small = img.reduce(8); m = small.convert("L").point([max(0, min(255, int((v - 185) * 3.6))) for v in range(256)])
        warm = Image.merge("RGB", (m, m.point([int(v * 0.42) for v in range(256)]), m.point([int(v * 0.16) for v in range(256)])))
        glow = warm.filter(ImageFilter.GaussianBlur(7)).point([min(255, int(v * hal * 1.3)) for v in range(256)] * 3).resize(img.size, Image.BILINEAR)
        img = ImageChops.screen(img, glow)
    if ab:
        s = max(1, int(round(ab))); r, g, b = img.split(); img = Image.merge("RGB", (ImageChops.offset(r, s, 0), g, ImageChops.offset(b, -s, 0)))
    if bloom:
        small = img.reduce(4); mask = small.convert("L").point(_lut("thresh", 0))
        bright = ImageChops.multiply(small, Image.merge("RGB", (mask, mask, mask)))
        glow = bright.filter(ImageFilter.GaussianBlur(5)).point(_lut("gain", round(bloom, 2)) * 3).resize(img.size, Image.BILINEAR)
        img = ImageChops.screen(img, glow)
    if grain:
        img = ImageChops.add(img, _grain(img.width, img.height, round(min(1.0, grain * 0.2), 3), frame_index % 8), 1.0, -128)
    return img


def apply_punch(img, t, punches, amount=0.028, dur=0.3):
    """A quick push-in on each beat in `punches` (absolute seconds): scale rises fast and eases back."""
    k = 0.0
    for p in punches:
        d = t - p
        if 0 <= d < dur: k = max(k, (1 - d / dur) ** 2)
    if k <= 0.002: return img
    W, H = img.size; z = 1 + amount * k; cw, ch = W / z, H / z
    return img.resize((W, H), Image.BICUBIC, box=((W - cw) / 2, (H - ch) / 2, (W + cw) / 2, (H + ch) / 2))


LOOKS = {
    "clean": {},
    "film": {"bloom": 0.30, "grain": 0.35, "aberration": 1},
    "neon": {"bloom": 0.60, "grain": 0.15, "aberration": 2},
    "soft": {"bloom": 0.20, "grain": 0.10},
    "cinema": {"bloom": 0.25, "halation": 0.55, "tone": True, "grain": 0.30, "aberration": 1},
}
MOTION = {                       # automatic camera for scenes that do not set their own
    "none": None,
    "calm": {"zoom": [1.0, 1.035], "drift": 0.25},
    "lively": {"zoom": [1.0, 1.07], "drift": 0.5},
}


def average(frames):
    """Average equally weighted PIL frames (motion blur accumulation)."""
    if len(frames) == 1: return frames[0]
    acc = np.zeros((frames[0].height, frames[0].width, 3), np.float32)
    for f in frames: acc += np.asarray(f, dtype=np.float32)
    return Image.fromarray((acc / len(frames) + 0.5).astype(np.uint8), "RGB")
