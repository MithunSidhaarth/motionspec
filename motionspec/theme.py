"""Themes: colours, fonts and brand identity as data. Nothing in the engine hardcodes a brand."""
import json
import os
from dataclasses import dataclass, field, fields
from functools import lru_cache

from PIL import ImageFont

BUILTIN = {
    "midnight": dict(bg="#0E1116", fg="#F3F4F6", muted="#9AA3B2", dim="#262C38", card="#171C26", accent="#FFB020",
                     accent_text="#0E1116", positive="#3DDC97", negative="#FF5D73"),
    "paper": dict(bg="#F6F4EF", fg="#14161A", muted="#5A6070", dim="#D9D5CA", card="#FFFFFF", accent="#C23B16",
                  accent_text="#FFFFFF", positive="#1F9D6B", negative="#C0392B"),
    "signal": dict(bg="#06121F", fg="#EAF6FF", muted="#86A5BD", dim="#14304A", card="#0C2236", accent="#2EE6D6",
                   accent_text="#06121F", positive="#7CFFB2", negative="#FF7A7A"),
}
FONT_CANDIDATES = {
    "bold": ["bahnschrift.ttf", "seguibl.ttf", "arialbd.ttf", "Inter-Bold.ttf", "DejaVuSans-Bold.ttf", "Helvetica.ttc"],
    "reg": ["bahnschrift.ttf", "segoeui.ttf", "arial.ttf", "Inter-Regular.ttf", "DejaVuSans.ttf", "Helvetica.ttc"],
    "mono": ["consola.ttf", "cour.ttf", "JetBrainsMono-Regular.ttf", "DejaVuSansMono.ttf", "Menlo.ttc"],
}
FONT_DIRS = ["C:/Windows/Fonts", "/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/truetype",
             "/System/Library/Fonts", "/System/Library/Fonts/Supplemental", os.path.expanduser("~/.fonts")]


class ThemeError(ValueError):
    """Raised for an invalid theme (bad colour, unknown key, missing font)."""


@lru_cache(maxsize=512)
def rgb(h):
    """'#RRGGBB' or '#RGB' -> (r, g, b). Raises ThemeError with the offending value."""
    if not isinstance(h, str): raise ThemeError(f"colour must be a hex string like '#FFB020', got {h!r}")
    s = h.lstrip("#")
    if len(s) == 3: s = "".join(c * 2 for c in s)
    if len(s) != 6 or any(c not in "0123456789abcdefABCDEF" for c in s):
        raise ThemeError(f"'{h}' is not a hex colour (use '#RRGGBB'). Theme colour names: bg, fg, muted, dim, card, accent, accent_text, positive, negative")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def luminance(c):
    def f(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (f(v) for v in rgb(c))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


@dataclass
class Theme:
    name: str = "midnight"
    bg: str = "#0E1116"
    fg: str = "#F3F4F6"
    muted: str = "#9AA3B2"
    dim: str = "#262C38"
    card: str = "#171C26"
    accent: str = "#FFB020"
    accent_text: str = "#0E1116"
    positive: str = "#3DDC97"
    negative: str = "#FF5D73"
    brand: str = ""          # shown on the end card; empty = no brand text
    tagline: str = ""
    url: str = ""
    logo: str = ""           # path to a PNG (transparent works best); empty = no logo
    fonts: dict = field(default_factory=dict)      # {"bold": "path/or/name.ttf", "reg": ..., "mono": ...}
    font_dirs: list = field(default_factory=list)
    grain: float = 0.0       # 0..1 film grain strength
    vignette: float = 0.0    # 0..1 edge darkening
    backdrop: str = "orbs"   # none | orbs | grid | dots: slow animated depth behind every scene
    base_dir: str = "."

    def font(self, kind, size):
        s = max(8, round(size * 2) / 2)            # quantise to 0.5 px so animated sizes do not flood the cache
        return _load_font(kind, int(round(s)), self.fonts.get(kind, ""), tuple(self.font_dirs), self.base_dir)

    def validate(self):
        for k in ("bg", "fg", "muted", "dim", "card", "accent", "accent_text", "positive", "negative"): rgb(getattr(self, k))
        return self

    def check(self):
        """Contrast notes for this theme (used by `motionspec doctor`)."""
        out = []
        for a, b, need in (("fg", "bg", 7), ("muted", "bg", 4.5), ("accent", "bg", 3), ("accent_text", "accent", 4.5)):
            r = contrast(getattr(self, a), getattr(self, b))
            if r < need: out.append(f"{a} on {b} contrast {r:.1f}:1 is below {need}:1")
        return out


_BUNDLED = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")


@lru_cache(maxsize=64)
def font_path(kind, custom="", extra_dirs=(), base_dir="."):
    """Resolve a font file for `kind` (bold|reg|mono): theme override, bundled fonts/, then system fallbacks."""
    names = ([custom] if custom else []) + FONT_CANDIDATES[kind]
    dirs = [base_dir, *extra_dirs, _BUNDLED, *FONT_DIRS]
    for n in names:
        for p in ([n] if os.path.isabs(n) else [os.path.join(d, n) for d in dirs]):
            if os.path.isfile(p): return p
    raise ThemeError(f"no '{kind}' font found. Put a .ttf in motionspec/fonts/, set theme.fonts.{kind}, or run `motionspec doctor`.")


@lru_cache(maxsize=512)
def _load_font(kind, size, custom, extra_dirs, base_dir):
    p = font_path(kind, custom, extra_dirs, base_dir)
    f = ImageFont.truetype(p, size)
    if kind == "bold" and "bahn" in p.lower():
        try: f.set_variation_by_name("Bold")
        except (OSError, ValueError): pass       # font has no variation axes: regular weight is acceptable
    return f


def load_theme(spec_theme, base_dir="."):
    """spec_theme: None | builtin name | path to .json | dict (optionally with "extends")."""
    if spec_theme is None: spec_theme = "midnight"
    if isinstance(spec_theme, str):
        if spec_theme in BUILTIN:
            data = {"name": spec_theme, **BUILTIN[spec_theme]}
        else:
            p = spec_theme if os.path.isabs(spec_theme) else os.path.join(base_dir, spec_theme)
            data = json.load(open(p, encoding="utf-8"))
            base_dir = os.path.dirname(os.path.abspath(p))
    else:
        data = dict(spec_theme)
    if "extends" in data:
        parent = BUILTIN.get(data["extends"], {})
        data = {**parent, **{k: v for k, v in data.items() if k != "extends"}}
    known = {f.name for f in fields(Theme)}
    bad = set(data) - known
    if bad: raise ThemeError(f"unknown theme keys: {sorted(bad)} (valid: {sorted(known)})")
    t = Theme(**data)
    t.base_dir = base_dir
    t.validate()
    if t.logo and not os.path.isabs(t.logo): t.logo = os.path.join(base_dir, t.logo)
    return t
