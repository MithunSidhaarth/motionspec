"""Output formats and the design-sheet mapping. Scenes author coordinates on a 1080x1920 sheet; Y()/S() map them."""
from dataclasses import dataclass

FORMATS = {
    "reel": (1080, 1920), "story": (1080, 1920), "short": (1080, 1920),
    "portrait": (1080, 1350), "square": (1080, 1080),
    "landscape": (1920, 1080), "landscape4k": (3840, 2160),
}


@dataclass(frozen=True)
class Format:
    name: str
    W: int
    H: int

    @property
    def u(self):
        """Type and graphics scale: 1.0 at 1080 wide on vertical formats, 0.95 per 1080 px of height on wide formats."""
        return self.H / 1080 * 0.95 if self.wide else min(self.W / 1080, self.H / 1440)

    @property
    def wide(self): return self.W / self.H > 1.2

    @property
    def tall(self): return self.H / self.W > 1.5

    def Y(self, y): return y * self.H / 1920                  # design-sheet y -> pixels

    def S(self, n): return n * self.u                         # design-sheet size -> pixels

    @property
    def safe(self):
        """(x0, y0, x1, y1) in pixels. Vertical video loses ~12% top and ~22% bottom to platform UI."""
        if self.tall: return (0.055 * self.W, 0.12 * self.H, 0.945 * self.W, 0.78 * self.H)
        return (0.05 * self.W, 0.07 * self.H, 0.95 * self.W, 0.93 * self.H)


def get_format(name):
    """A preset name (see FORMATS) or an explicit 'WIDTHxHEIGHT'."""
    if name in FORMATS: return Format(name, *FORMATS[name])
    try:
        w, h = (int(v) for v in name.lower().split("x"))
        if w < 64 or h < 64 or w % 2 or h % 2: raise ValueError
        return Format(name, w, h)
    except ValueError:
        raise ValueError(f"unknown format '{name}'. Use one of {sorted(FORMATS)} or an even WIDTHxHEIGHT such as 1280x720.") from None
