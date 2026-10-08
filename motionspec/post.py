"""Per-scene camera and per-frame post effects. All deterministic: the same (spec, frame index) always gives the same pixels."""
from functools import lru_cache

import numpy as np
from PIL import Image, ImageFilter

from .ease import drift, in_out, lerp, prog


def apply_camera(img, cam, t, dur):
    """cam: {"zoom": [from, to], "pan": [dx0, dy0, dx1, dy1] (fractions of the frame), "drift": 0..1 handheld wobble}.
    Implemented as a sub-pixel crop-and-resize of the finished scene, so every scene gets a camera for free."""
    if not cam: return img
    W, H = img.size; k = in_out(prog(t, 0, dur)); z0, z1 = cam.get("zoom", [1.0, 1.0])
    z = max(1.0, lerp(z0, z1, k)); pan = cam.get("pan", [0, 0, 0, 0]); w = float(cam.get("drift", 0.0))
    dx = lerp(pan[0], pan[2], k) * W + w * 0.012 * W * drift(t, 1.3); dy = lerp(pan[1], pan[3], k) * H + w * 0.012 * H * drift(t, 4.1)
    cw, ch = W / z, H / z
    l = min(max((W - cw) / 2 + dx, 0), W - cw); tp = min(max((H - ch) / 2 + dy, 0), H - ch)
    return img.resize((W, H), Image.BICUBIC, box=(l, tp, l + cw, tp + ch))


@lru_cache(maxsize=4)
def _grain_tiles(W, H, n=8):
    rng = np.random.default_rng(11)
    return [rng.normal(0, 1, (H, W, 1)).astype(np.float32) for _ in range(n)]


def post(img, cfg, frame_index):
    """cfg: {"bloom": 0..1, "grain": 0..1, "aberration": px}. Returns a new PIL image (or the same one when nothing is enabled)."""
    if not cfg: return img
    bloom, grain, ab = cfg.get("bloom", 0), cfg.get("grain", 0), cfg.get("aberration", 0)
    if not (bloom or grain or ab): return img
    a = np.asarray(img, dtype=np.float32)
    if ab:
        s = int(round(ab)); a = np.stack([np.roll(a[..., 0], s, 1), a[..., 1], np.roll(a[..., 2], -s, 1)], -1)
    if bloom:
        lum = a.mean(-1, keepdims=True); mask = np.clip((lum - 170) / 85, 0, 1) * a
        small = Image.fromarray(mask.astype(np.uint8)).reduce(4).filter(ImageFilter.GaussianBlur(6))
        glow = np.asarray(small.resize(img.size, Image.BILINEAR), dtype=np.float32)
        a = 255 - (255 - a) * (255 - glow * bloom) / 255          # screen blend
    if grain:
        tiles = _grain_tiles(img.width, img.height); a = a + tiles[frame_index % len(tiles)] * (255 * 0.03 * grain)
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGB")


def average(frames):
    """Average equally weighted PIL frames (motion blur accumulation)."""
    if len(frames) == 1: return frames[0]
    acc = np.zeros((frames[0].height, frames[0].width, 3), np.float32)
    for f in frames: acc += np.asarray(f, dtype=np.float32)
    return Image.fromarray((acc / len(frames) + 0.5).astype(np.uint8), "RGB")
