"""Text scenes: title, section, bullets, steps, quote, note."""
import math

from .. import sync
from ..ease import in_out, out_back, out_cubic, prog, spring, stagger
from . import scene


def _tokens(line):
    """'Make it *pop* now' -> [('Make', False), ('it', False), ('pop', True), ('now', False)]. Emphasis can span words: '*a video*'."""
    out, on = [], False
    for w in line.split():
        start = w.startswith("*"); end = w.rstrip(".,!?;:").endswith("*") and len(w.rstrip(".,!?;:")) > (1 if start else 0)
        if start: on = True
        out.append((w.replace("*", ""), on))
        if end: on = False
    return out


def _title_times(s):
    """When each title unit appears: on the spoken word when narrated, else on a steady beat."""
    step = s.get("step", 0.22)
    if s.get("style", "lines") == "lines" and not any("*" in ln for ln in s.get("lines", [])):
        return sync.sequence(s, s.get("lines", []), 0.15, step)
    return sync.sequence(s, [w for ln in s.get("lines", []) for w, _ in _tokens(ln)], 0.15, step * 0.6)


@scene("title", fields={"lines": (list, True), "accent": (int, False), "size": ((int, float), False), "kicker": (str, False),
                        "subtitle": (str, False), "step": ((int, float), False), "style": (str, False), "underline": (bool, False)},
       cues=lambda s: [(t, "key" if s.get("style") in ("words", "letters") else "tick") for t in _title_times(s)],
       desc="Big headline. `style`: lines (default) | words (each word stretches and springs in) | letters (kinetic). *asterisks* colour words with the accent; `underline` draws a line under it. With narration each word appears when it is spoken.")
def title(c, t, s):
    size = s.get("size", 112); y = c.Y(560) if c.tall else c.H * (0.40 if c.wide else 0.36); style = s.get("style", "lines"); step = s.get("step", 0.22)
    px = c.S(size); times = _title_times(s)
    if s.get("kicker"): c.text(c.cx, y - c.S(110), s["kicker"], "mono", 36, "muted", prog(t, 0.0, 0.5))
    n_word = 0; y_last = y; w_last = 0
    for i, raw in enumerate(s["lines"]):
        toks = _tokens(raw); line = " ".join(w for w, _ in toks); wrapped = c.wrap(line, "bold", px, c.W * 0.9)
        if style == "lines" and not any(em for _, em in toks):
            p = out_cubic(prog(t, times[i], 0.55))
            c.text(c.cx, y, wrapped, "bold", size, "accent" if i == s.get("accent") else "fg", min(1, p * 3), dy=(1 - p) * c.S(size * 0.9), reveal=True)
            y_last, w_last = y, c.text_size(wrapped, "bold", size)[0]; y += c.S(size * 1.25) * (1 + wrapped.count(chr(10))); continue
        f = c.font("bold", px); space = f.getlength(" "); total = sum(f.getlength(w) for w, _ in toks) + space * (len(toks) - 1)
        x = c.cx - total / 2; w_last = total; y_last = y
        for w, em in toks:
            col = "accent" if (em or i == s.get("accent")) else "fg"; wl = f.getlength(w); t0 = times[min(n_word, len(times) - 1)]
            if style == "letters":
                lx = x
                for j, ch in enumerate(w):
                    k = spring(prog(t, t0 + j * 0.035, 0.7), 0.5, 2.2); cw = f.getlength(ch)
                    c.text(lx + cw / 2, y, ch, "bold", size, col, min(1, k * 3), anchor="ma", dy=(1 - min(1, k)) * px * 0.95, reveal=True, width=75 + 25 * min(1, k))
                    lx += cw
            else:
                k = spring(prog(t, t0, 0.7), 0.5, 2.2)
                c.text(x + wl / 2, y, w, "bold", size, col, min(1, k * 3), anchor="ma", dy=(1 - min(1, k)) * px * 0.95, reveal=True, width=75 + 25 * min(1, k))
            x += wl + space; n_word += 1
        y += c.S(size * 1.25)
    if s.get("underline"):
        u = in_out(prog(t, (times[-1] if times else 0.3) + 0.35, 0.5)); yy = y_last + c.S(size) * 1.15
        c.line([(c.cx - w_last / 2, yy), (c.cx - w_last / 2 + w_last * u, yy)], max(2, c.S(size) * 0.06), "accent")
    if s.get("subtitle"):
        c.text(c.cx, y + c.S(30), c.fit(s["subtitle"], "reg", 48, 0.8), "reg", 48, "muted", prog(t, (times[-1] if times else 0.3) + 0.5, 0.5))


@scene("section", fields={"number": ((int, str), False), "title": (str, True), "subtitle": (str, False)},
       cues=lambda s: [(0.1, "whoosh"), (0.45, "impact", -8)], desc="Chapter card: big number, title, optional subtitle.")
def section(c, t, s):
    p = out_cubic(prog(t, 0.1, 0.6)); y = c.H * 0.36
    if s.get("number") is not None:
        c.text(c.cx, y, str(s["number"]), "bold", 300, "accent", p, dy=(1 - p) * c.S(50)); y += c.S(330)
    c.text(c.cx, y, c.fit(s["title"], "bold", 84, 0.86), "bold", 84, "fg", prog(t, 0.35, 0.5))
    if s.get("subtitle"): c.text(c.cx, y + c.S(190), c.fit(s["subtitle"], "reg", 44, 0.8), "reg", 44, "muted", prog(t, 0.7, 0.5))


def _item_times(s):
    items = s.get("items") or s.get("steps") or []
    return sync.sequence(s, [(i["head"] if isinstance(i, dict) else i) for i in items], 0.55, 0.5)


@scene("bullets", fields={"title": (str, False), "items": (list, True), "numbered": (bool, False)},
       cues=lambda s: [(0.1, "swish", -9)] + [(t, "tick") for t in _item_times(s)] + [(t + 0.08, "pop", -8) for t in _item_times(s)],
       desc="List that builds item by item, each on the spoken word when narrated. Items are strings or {head, sub}.")
def bullets(c, t, s):
    items = [i if isinstance(i, dict) else {"head": i} for i in s["items"]]
    if not items: return
    times = _item_times(s)
    if s.get("title"): c.text(c.cx, c.H * 0.15, c.fit(s["title"], "bold", 70, 0.86), "bold", 70, "fg", out_cubic(prog(t, 0.1, .5)))
    n = len(items); top, bot = c.H * 0.22, c.H * (0.76 if c.tall else 0.88)
    step = min(c.S(230), (bot - top) / n); block = (n - 1) * step + c.S(120); y = top + max(0.0, ((bot - top) - block) / 2); left = c.W * (0.12 if not c.wide else 0.2)
    for k, it in enumerate(items):
        p = out_cubic(prog(t, times[k], 0.55))
        if s.get("numbered"):
            c.dot(left, y + c.S(34), c.S(36) * p, "accent"); c.text(left, y + c.S(34), str(k + 1), "bold", 40, "accent_text", p, anchor="mm")
        else:
            c.dot(left, y + c.S(34), c.S(12) * p, "accent")
        x = left + c.S(70); w = c.W - x - c.W * 0.07
        c.text(x, y, c.wrap(it["head"], "bold", c.S(54), w), "bold", 54, "fg", min(1, p * 3), anchor="la", dy=(1 - p) * c.S(50), reveal=True)
        if it.get("sub"):
            c.text(x, y + c.S(76), c.wrap(it["sub"], "reg", c.S(36), w), "reg", 36, "muted", p, anchor="la", dy=(1 - p) * c.S(40))
        y += step


@scene("steps", fields={"title": (str, False), "steps": (list, True)},
       cues=lambda s: [(0.1, "swish", -9)] + [(t, "tick") for t in _item_times(s)] + [(t + 0.08, "pop", -8) for t in _item_times(s)],
       desc="Numbered process. Same as bullets with numbers; `steps` are strings or {head, sub}.")
def steps(c, t, s):
    bullets(c, t, {"title": s.get("title"), "items": s["steps"], "numbered": True})


@scene("quote", fields={"text": (str, True), "who": (str, False), "role": (str, False)},
       cues=lambda s: [(0.15, "swish", -8), (0.9, "pop")], desc="Pull quote with attribution.")
def quote(c, t, s):
    p = out_cubic(prog(t, 0.15, 0.7)); mx = c.W * 0.84
    body = c.wrap(s["text"], "bold", c.S(70), mx)
    c.text(c.W * 0.08, c.H * 0.2, "“", "bold", 400, "accent", p, anchor="la")
    c.text(c.W * 0.08, c.H * 0.36, body, "bold", 70, "fg", p, anchor="la", dy=(1 - p) * c.S(30), spacing=14)
    h = (body.count("\n") + 1) * c.S(98)
    if s.get("who"):
        c.text(c.W * 0.08, c.H * 0.36 + h + c.S(40), s["who"], "bold", 44, "accent", prog(t, 0.9, .4), anchor="la")
        if s.get("role"): c.text(c.W * 0.08, c.H * 0.36 + h + c.S(100), s["role"], "reg", 36, "muted", prog(t, 1.0, .4), anchor="la")


@scene("note", fields={"kicker": (str, False), "text": (str, True), "small": (str, False)},
       cues=lambda s: [(0.15, "swish", -8), (0.45, "stamp", -6)], desc="Boxed callout for a caveat, definition or key line. `kicker`, `text`, `small`.")
def note(c, t, s):
    p = out_cubic(prog(t, 0.2, 0.6)); x0, x1 = c.W * 0.07, c.W * 0.93; w = x1 - x0 - c.S(110)
    body = c.wrap(s["text"], "bold", c.S(74), w); sub = c.wrap(s["small"], "reg", c.S(36), w) if s.get("small") else ""
    h = c.S(190) + (body.count("\n") + 1) * c.S(92) + ((sub.count("\n") + 1) * c.S(48) + c.S(40) if sub else 0)
    y0 = c.H / 2 - h / 2 + math.sin(t * 1.7) * c.S(9) * min(1, max(0.0, t - 1.0))               # the settled card floats
    c.shadow_rect((x0, y0, x1, y0 + h), c.S(36), c.S(30), 0.45 * p); c.rect((x0, y0, x1, y0 + h), "card", radius=c.S(36)); c.rect((x0, y0, x0 + c.S(16), y0 + h), "accent")
    if s.get("kicker"): c.text(x0 + c.S(70), y0 + c.S(40), s["kicker"], "mono", 34, "accent", p, anchor="la")
    c.text(x0 + c.S(70), y0 + c.S(110), body, "bold", 74, "fg", p, anchor="la", dy=(1 - p) * c.S(30))
    if sub: c.text(x0 + c.S(70), y0 + c.S(130) + (body.count("\n") + 1) * c.S(92), sub, "reg", 36, "muted", prog(t, 1.0, .5), anchor="la")
