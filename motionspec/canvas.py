"""Canvas: the drawing surface handed to every scene. Anti-aliased primitives, measured text with an overflow guard,
backgrounds (solid / gradient / vignette). One Canvas per frame; no global mutable state, so frames render in parallel."""
import math
from functools import lru_cache

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from .theme import ThemeError, luminance, rgb

SS = 3  # supersampling for shapes (box-filtered down)
_COLORS = {"bg", "fg", "muted", "dim", "card", "accent", "accent_text", "positive", "negative"}


@lru_cache(maxsize=16)
def _background(W, H, bg, grad, vignette):
    base = np.zeros((H, W, 3), np.float32); base[:] = rgb(bg)
    if grad:
        k = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
        base = np.array(rgb(grad[0]), np.float32) * (1 - k) + np.array(rgb(grad[1]), np.float32) * k
        base = np.broadcast_to(base, (H, W, 3)).copy()
        # tiny deterministic dither: stops banding on dark gradients
        base += np.random.default_rng(3).uniform(-0.5, 0.5, (H, W, 1)).astype(np.float32)
    if vignette:
        y, x = np.mgrid[0:H, 0:W].astype(np.float32)
        d = np.sqrt(((x - W / 2) / (W / 2)) ** 2 + ((y - H / 2) / (H / 2)) ** 2) / math.sqrt(2)
        base *= (1 - vignette * np.clip(d, 0, 1) ** 2.2)[..., None]
    return Image.fromarray(np.clip(base, 0, 255).astype(np.uint8), "RGB").tobytes()


@lru_cache(maxsize=512)
def _dot_sprite(r10):
    r = r10 / 10; n = int(math.ceil(r)) * 2 + 3
    m = Image.new("L", (n * SS, n * SS), 0); c = n * SS / 2
    ImageDraw.Draw(m).ellipse((c - r * SS, c - r * SS, c + r * SS, c + r * SS), fill=255)
    return m.reduce(SS)


@lru_cache(maxsize=1024)
def _text_mask(s, font, spacing, anchor, align):
    """Rasterise text once -> (L mask, (left, top) offset of the mask relative to the anchor point)."""
    d = ImageDraw.Draw(Image.new("L", (4, 4)))
    ml = "\n" in s
    bb = (d.multiline_textbbox((0, 0), s, font=font, anchor=anchor if not ml or anchor[1] != "m" else anchor[0] + "a", spacing=spacing, align=align)
          if ml else d.textbbox((0, 0), s, font=font, anchor=anchor))
    pad = 4
    x0, y0, x1, y1 = int(bb[0]) - pad, int(bb[1]) - pad, int(math.ceil(bb[2])) + pad, int(math.ceil(bb[3])) + pad
    m = Image.new("L", (max(1, x1 - x0), max(1, y1 - y0)), 0); md = ImageDraw.Draw(m)
    if ml:
        a = anchor if anchor[1] != "m" else anchor[0] + "a"
        md.multiline_text((-x0, -y0), s, font=font, fill=255, anchor=a, spacing=spacing, align=align)
    else:
        md.text((-x0, -y0), s, font=font, fill=255, anchor=anchor)
    return m, (x0, y0)


class Canvas:
    def __init__(self, fmt, theme, bg=None, gradient=None, warnings=None):
        self.fmt, self.theme = fmt, theme
        self.W, self.H, self.u, self.wide, self.tall = fmt.W, fmt.H, fmt.u, fmt.wide, fmt.tall
        self.warnings = warnings if warnings is not None else []
        self.light = luminance(theme.bg) > 0.5          # light themes get much softer shadows
        raw = _background(fmt.W, fmt.H, bg if bg and bg.startswith("#") else getattr(theme, bg or "bg"),
                          tuple(gradient) if gradient else None, round(theme.vignette, 3))
        self.img = Image.frombytes("RGB", (fmt.W, fmt.H), raw)

    # ---- layout helpers
    def Y(self, y): return self.fmt.Y(y)
    def S(self, n): return self.fmt.S(n)
    @property
    def cx(self): return self.W / 2
    @property
    def safe(self): return self.fmt.safe
    def col(self, c):
        if isinstance(c, tuple): return c
        return rgb(getattr(self.theme, c)) if c in _COLORS else rgb(c)

    # ---- text
    def font(self, kind, size): return self.theme.font(kind, size)

    def wrap(self, s, kind, size, max_w):
        """Greedy word wrap measured with the real font so it re-flows on any format. `size` is in pixels."""
        return _wrap(str(s), self.font(kind, size), float(max_w))

    def fit(self, s, kind, size, frac=0.86):
        """Wrap a string for a design-sheet font size to `frac` of the frame width."""
        return self.wrap(s, kind, self.S(size), self.W * frac)

    def text_size(self, s, kind, size, spacing=10):
        m, _ = _text_mask(s, self.font(kind, self.S(size)), int(self.S(spacing)), "la", "left")
        return m.width - 8, m.height - 8

    def text(self, x, y, s, kind="bold", size=64, color="fg", alpha=1.0, anchor="ma", dy=0, spacing=10,
             shadow=0.0, scale=1.0, tracking=0.0, reveal=False):
        """Draw text. `size`/`spacing`/`dy` are design-sheet units except dy which is pixels. `shadow` 0..1 adds a soft drop shadow.
        Sub-pixel positions are honoured by resampling the cached mask, so slow slides do not jitter."""
        if alpha <= 0.004 or not s: return
        s = str(s); f = self.font(kind, self.S(size) * scale); sp = int(self.S(spacing))
        align = "center" if anchor[0] == "m" else ("right" if anchor[0] == "r" else "left")
        m, (ox, oy) = _text_mask(s, f, sp, anchor, align)
        if reveal and dy > 0:                       # text rises out of an invisible line at the bottom of its final box
            keep = int(m.height - dy)
            if keep <= 0: return
            m = m.crop((0, 0, m.width, keep))
        px, py = x + ox, y + dy + oy; ix, iy = math.floor(px), math.floor(py); fx, fy = px - ix, py - iy
        if fx > 0.02 or fy > 0.02:
            m = m.transform((m.width + 1, m.height + 1), Image.AFFINE, (1, 0, -fx, 0, 1, -fy), resample=Image.BILINEAR)
        if shadow and self.light: shadow *= 0.22
        if shadow:
            key = (s, id(f), sp, anchor, round(fx, 1), round(fy, 1), int(self.S(10)))
            base = _SHADOWS.get(key)
            if base is None:
                if len(_SHADOWS) > 256: _SHADOWS.clear()
                base = _SHADOWS[key] = m.filter(ImageFilter.GaussianBlur(int(self.S(10))))
            sh = base.point(lambda v: int(v * 0.65 * shadow * alpha))
            self._paste_l(sh, ix, iy + int(self.S(6)), (0, 0, 0))
        if alpha < 1: m = m.point(lambda v: int(v * alpha))
        self._paste_l(m, ix, iy, self.col(color))
        sx0, sy0, sx1, sy1 = self.safe
        if m.width > (sx1 - sx0) * 1.04 and alpha > 0.5:
            self.warnings.append(f"text wider than the safe area: '{s.splitlines()[0][:40]}'")

    def _paste_l(self, mask, x, y, color):
        x0, y0 = max(0, x), max(0, y); x1, y1 = min(self.W, x + mask.width), min(self.H, y + mask.height)
        if x1 <= x0 or y1 <= y0: return
        m = mask.crop((x0 - x, y0 - y, x1 - x, y1 - y))
        self.img.paste(Image.new("RGB", m.size, color), (x0, y0), m)

    # ---- shapes
    def _shape(self, box, draw_fn, color, alpha):
        x0, y0 = int(math.floor(box[0])) - 2, int(math.floor(box[1])) - 2
        x1, y1 = int(math.ceil(box[2])) + 2, int(math.ceil(box[3])) + 2
        cx0, cy0, cx1, cy1 = max(0, x0), max(0, y0), min(self.W, x1), min(self.H, y1)
        if cx1 <= cx0 or cy1 <= cy0 or alpha <= 0: return
        w, h = cx1 - cx0, cy1 - cy0
        m = Image.new("L", (w * SS, h * SS), 0)
        draw_fn(ImageDraw.Draw(m), cx0, cy0)
        m = m.reduce(SS)
        if alpha < 1: m = m.point(lambda v: int(v * alpha))
        self.img.paste(Image.new("RGB", m.size, self.col(color)), (cx0, cy0), m)

    def rect(self, box, color="card", alpha=1.0, radius=0):
        if box[2] <= box[0] or box[3] <= box[1]: return
        r = min(radius, (box[2] - box[0]) / 2, (box[3] - box[1]) / 2)
        self._shape(box, lambda d, ox, oy: d.rounded_rectangle(
            ((box[0] - ox) * SS, (box[1] - oy) * SS, (box[2] - ox) * SS - 1, (box[3] - oy) * SS - 1), radius=r * SS, fill=255), color, alpha)

    def dot(self, x, y, r, color="accent", alpha=1.0):
        """Filled circle. Uses a cached sprite per radius (10th-of-a-pixel precision): thousands per frame stay cheap."""
        if r < 0.5 or alpha <= 0: return
        sp = _dot_sprite(int(round(r * 10))); ix, iy = int(round(x - sp.width / 2)), int(round(y - sp.height / 2))
        if alpha < 1: sp = sp.point(lambda v: int(v * alpha))
        self._paste_l(sp, ix, iy, self.col(color))

    def line(self, pts, width, color="accent", alpha=1.0):
        """Polyline through pts with round caps; `width` in pixels."""
        if len(pts) < 2: return
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]; w2 = width / 2 + 2
        box = (min(xs) - w2, min(ys) - w2, max(xs) + w2, max(ys) + w2)

        def fn(d, ox, oy):
            q = [((x - ox) * SS, (y - oy) * SS) for x, y in pts]
            d.line(q, fill=255, width=max(1, int(width * SS)), joint="curve")
            r = width * SS / 2
            for px, py in (q[0], q[-1]): d.ellipse((px - r, py - r, px + r, py + r), fill=255)
        self._shape(box, fn, color, alpha)

    def arc(self, cx, cy, r, a0, a1, width, color="accent", alpha=1.0):
        box = (cx - r - width, cy - r - width, cx + r + width, cy + r + width)
        self._shape(box, lambda d, ox, oy: d.arc(((cx - r - ox) * SS, (cy - r - oy) * SS, (cx + r - ox) * SS, (cy + r - oy) * SS),
                                                 a0, a1, fill=255, width=max(1, int(width * SS))), color, alpha)

    def glow(self, x, y, r, color="accent", alpha=0.35):
        """Soft radial glow centred at x, y (cached per radius and alpha step)."""
        g = _glow_scaled(max(8, int(r) // 4 * 4), int(round(min(1.0, alpha) * 40))); self._paste_l(g, int(x - g.width / 2), int(y - g.height / 2), self.col(color))

    def shadow_rect(self, box, radius=0, blur=24, alpha=0.5, dy=12):
        """Soft drop shadow under a rounded rectangle (call before drawing the rectangle)."""
        b = max(2, int(blur)); pad = b * 2; x0, y0, x1, y1 = [int(v) for v in box]
        w, h = x1 - x0 + pad * 2, y1 - y0 + pad * 2
        if w <= 0 or h <= 0: return
        q = 4; m = Image.new("L", (max(1, w // q), max(1, h // q)), 0)
        ImageDraw.Draw(m).rounded_rectangle((pad // q, pad // q, (pad + x1 - x0) // q, (pad + y1 - y0) // q), radius=max(1, int(radius) // q), fill=int(255 * alpha))
        m = m.filter(ImageFilter.GaussianBlur(max(1, b // q))).resize((w, h), Image.BILINEAR)
        self._paste_l(m, x0 - pad, y0 - pad + int(dy), (0, 0, 0))

    # ---- images
    def paste_image(self, im, x, y, alpha=1.0, radius=0):
        im = im.convert("RGBA"); a = im.getchannel("A")
        if radius:
            m = Image.new("L", im.size, 0); ImageDraw.Draw(m).rounded_rectangle((0, 0, im.width - 1, im.height - 1), radius=int(radius), fill=255)
            a = ImageChops.multiply(a, m)
        if alpha < 1: a = a.point(lambda v: int(v * alpha))
        self.img.paste(im.convert("RGB"), (int(x), int(y)), a)

    def logo(self, cx, cy, size, alpha=1.0):
        """Theme logo (PNG) scaled to `size` px tall, centred. Returns False (and draws nothing) when the theme has no logo."""
        if not self.theme.logo or size < 8: return False
        im = _logo(self.theme.logo, int(size)); self.paste_image(im, cx - im.width / 2, cy - im.height / 2, alpha); return True


def _wrap(s, font, max_w):
    return _wrap_cached(s, font, max_w)


@lru_cache(maxsize=2048)
def _wrap_cached(s, font, max_w):
    out, line = [], ""
    for w in s.split():
        cand = (line + " " + w).strip()
        if font.getlength(cand) > max_w and line: out.append(line); line = w
        else: line = cand
    return "\n".join(out + [line])


_SHADOWS = {}


@lru_cache(maxsize=96)
def _glow_scaled(r, a40):
    return _glow_sprite(r).point(lambda v: int(v * a40 / 40))


@lru_cache(maxsize=32)
def _glow_sprite(r):
    n = r * 2 + 1; y, x = np.mgrid[0:n, 0:n].astype(np.float32)
    d = np.sqrt((x - r) ** 2 + (y - r) ** 2) / r
    return Image.fromarray((np.clip(1 - d, 0, 1) ** 2 * 255).astype(np.uint8), "L")


@lru_cache(maxsize=32)
def _logo(path, h):
    try: im = Image.open(path).convert("RGBA")
    except OSError as e: raise ThemeError(f"cannot open logo '{path}': {e}") from None
    return im.resize((max(1, int(im.width * h / im.height)), h), Image.LANCZOS)
