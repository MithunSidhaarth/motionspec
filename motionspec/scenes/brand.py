"""Brand scenes: endcard (logo, name, tagline, optional button, url) and slam/strike for hooks. Brand text comes from the theme."""
from ..ease import in_out, out_back, out_cubic, out_expo, prog, punch, spring
from . import scene


@scene("endcard", fields={"brand": (str, False), "tagline": (str, False), "url": (str, False), "button": (str, False),
                          "ask": (str, False), "loop": (bool, False)},
       cues=lambda s: [(0.1, "rise"), (1.2, "pop")],
       desc="End card: theme logo, brand name, tagline, optional pulsing button, url. Text defaults come from the theme.")
def endcard(c, t, s):
    th = c.theme; brand = s.get("brand", th.brand); tagline = s.get("tagline", th.tagline); url = s.get("url", th.url)
    p = spring(prog(t, 0.1, 0.9)); cy = c.H * (0.33 if not c.wide else 0.30); y = cy
    had_logo = c.logo(c.cx, cy, c.S(220) * max(p, 0.01), min(1, p * 2))
    if had_logo: y = cy + c.S(190)
    if brand:
        c.text(c.cx, y, brand, "bold", 120, "fg", prog(t, 0.5, .5)); y += c.S(170)
    if tagline:
        txt = c.fit(tagline, "reg", 46, 0.8); c.text(c.cx, y, txt, "reg", 46, "muted", prog(t, 0.8, .5)); y += c.S(70) * (1 + txt.count("\n")) + c.S(70)
    if s.get("button"):
        a = prog(t, 1.1, .5); k = punch(t, 1.1, 0.4, 0.06) * (1 + 0.025 * __import__("math").sin(max(0, t - 1.8) * 4))
        w = max(c.S(520), c.text_size(s["button"], "bold", 50)[0] + c.S(120)) * k; h = c.S(120) * k
        c.rect((c.cx - w / 2, y, c.cx + w / 2, y + h), "accent", a, radius=h / 2)
        c.text(c.cx, y + h / 2 - c.S(30), s["button"], "bold", 50, "accent_text", a); y += c.S(180)
    if url: c.text(c.cx, y, url, "mono", 48, "accent", prog(t, 1.2, .5)); y += c.S(100)
    if s.get("ask"): c.text(c.cx, y, c.fit(s["ask"], "reg", 36, 0.8), "reg", 36, "fg", prog(t, 1.5, .5))


@scene("slam", fields={"words": (list, True), "invert": (bool, False), "size": ((int, float), False), "hold": ((int, float), False)},
       cues=lambda s: [(0.15 + i * s.get("hold", 0.6), "thud") for i in range(len(s.get("words", [])))],
       desc="Full-frame word slams, one per beat, on an inverted (accent) field. `words`: [str], `hold` seconds per word.")
def slam(c, t, s):
    words = s["words"]; hold = s.get("hold", 0.6)
    if not words: return
    i = min(len(words) - 1, int(max(0, t - 0.15) / hold)); lt = max(0, t - 0.15 - i * hold)
    if s.get("invert", True): c.rect((0, 0, c.W, c.H), "accent")
    k = 1 + 0.18 * (1 - out_expo(prog(lt, 0, 0.25)))
    c.text(c.cx, c.H * 0.5 - c.S(s.get("size", 220)) * 0.6, c.wrap(words[i], "bold", c.S(s.get("size", 220)), c.W * 0.9), "bold",
           s.get("size", 220), "accent_text" if s.get("invert", True) else "fg", min(1.0, lt / 0.06 + 0.2), scale=k)


@scene("strike", fields={"wrong": (str, True), "right": (str, True), "kicker": (str, False)},
       cues=lambda s: [(0.9, "whoosh"), (1.5, "thud")],
       desc="Myth vs fact: the wrong claim gets a pen strike drawn through it, then the correct line slams in below.")
def strike(c, t, s):
    y = c.H * 0.34
    if s.get("kicker"): c.text(c.cx, y - c.S(120), s["kicker"], "mono", 36, "muted", prog(t, 0.0, .4))
    txt = c.fit(s["wrong"], "bold", 76, 0.86); a = out_cubic(prog(t, 0.1, 0.5))
    c.text(c.cx, y, txt, "bold", 76, "muted", a)
    w, h = c.text_size(txt, "bold", 76); k = in_out(prog(t, 0.9, 0.4)); ly = y + h * 0.5
    c.line([(c.cx - w / 2 - c.S(20), ly + c.S(8)), (c.cx - w / 2 - c.S(20) + (w + c.S(40)) * k, ly - c.S(10) * k)], c.S(14), "negative")
    q = out_back(prog(t, 1.5, 0.45))
    c.text(c.cx, c.H * 0.58, c.fit(s["right"], "bold", 96, 0.86), "bold", 96, "accent", min(1, q * 2), scale=0.85 + 0.15 * q)
