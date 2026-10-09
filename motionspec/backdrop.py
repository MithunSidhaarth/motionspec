"""Animated backdrops: slow, low-contrast motion behind every scene so frames never feel flat. Pure function of absolute time.
Glows are computed at one eighth resolution and scaled up (they are blurry anyway), which keeps them cheap."""
import math

import numpy as np
from PIL import Image, ImageChops

STYLES = ("none", "orbs", "grid", "dots")
_ORBS = ((0.18, 0.20, 0.62, 0.16, "accent"), (0.85, 0.78, 0.55, 0.12, "accent"), (0.55, 0.50, 0.75, 0.07, "muted"))


def draw(c, t, style):
    """Draw the backdrop onto canvas `c` at absolute time `t` (seconds)."""
    if style in (None, "none"): return
    W, H = c.W, c.H
    if style == "orbs":
        sw, sh = max(8, W // 8), max(8, H // 8); y, x = np.mgrid[0:sh, 0:sw].astype(np.float32); big = max(sw, sh); layers = []
        for i, (fx, fy, r, a, col) in enumerate(_ORBS):
            cx = sw * (fx + 0.07 * math.sin(t * 0.21 + i * 2.1)); cy = sh * (fy + 0.06 * math.cos(t * 0.17 + i * 1.3))
            d = np.sqrt((x - cx) ** 2 + (y - cy) ** 2) / (big * r)
            field = np.clip(1 - d, 0, 1) ** 2 * a
            layers.append(field[..., None] * np.array(c.col(col), np.float32))
        small = np.clip(sum(layers), 0, 255).astype(np.uint8)
        c.img = ImageChops.add(c.img, Image.fromarray(small, "RGB").resize((W, H), Image.BILINEAR))
    elif style in ("grid", "dots"):
        step = c.S(90); ox = (t * c.S(8)) % step; oy = (t * c.S(5)) % step
        y = -step + oy
        while y < H + step:
            x = -step + ox
            while x < W + step:
                if style == "dots": c.dot(x, y, c.S(2.2), "dim", 0.9)
                x += step
            if style == "grid": c.line([(0, y), (W, y)], max(1, c.S(1.2)), "dim", 0.5)
            y += step
        if style == "grid":
            x = -step + ox
            while x < W + step: c.line([(x, 0), (x, H)], max(1, c.S(1.2)), "dim", 0.5); x += step
