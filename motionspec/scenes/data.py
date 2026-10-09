"""Data scenes: stat, bars, chart, grid, compare, timeline."""
import math
from functools import lru_cache

from ..ease import in_out, lerp, out_back, out_cubic, prog, punch
from . import scene


def _num(v, decimals, commas):
    decimals = max(0, int(decimals))
    return f"{v:,.{decimals}f}" if commas else f"{v:.{decimals}f}"


def _nice_decimals(lo, hi):
    """Decimals needed so axis labels stay distinct for a given value range."""
    span = abs(hi - lo)
    return 0 if span >= 5 else 1 if span >= 0.5 else 2 if span >= 0.05 else 3


def _source(c, s, t):
    """Optional footer: {"source": "CPPP award records, 2023-26"} on any data scene."""
    if s.get("source"):
        c.text(c.cx, c.safe[3] if not c.tall else c.H * 0.86, "Source: " + s["source"], "mono", 28, "muted", prog(t, 0.8, .5))


_SRC = {"source": (str, False)}


@scene("stat", fields={**_SRC, "value": ((int, float), True), "prefix": (str, False), "suffix": (str, False), "decimals": (int, False),
                       "commas": (bool, False), "title": (str, False), "caption": (str, False), "size": ((int, float), False)},
       cues=lambda s: [(0.2, "rise"), (1.4, "tick")], desc="One big number that counts up, with a title above and a caption below.")
def stat(c, t, s):
    v = s["value"] * in_out(prog(t, 0.2, 1.1))
    shown = f'{s.get("prefix", "")}{_num(v, s.get("decimals", 0), s.get("commas", False))}{s.get("suffix", "")}'
    c.text(c.cx, c.Y(520) if not c.wide else c.H * .16, c.fit(s.get("title", ""), "mono", 36), "mono", 36, "muted", prog(t, 0.1, .4))
    ny = c.Y(700) if not c.wide else c.H * .26
    c.glow(c.cx, ny + c.S(s.get("size", 300)) * 0.5, c.S(s.get("size", 300)) * 1.6, "accent", 0.16 * prog(t, 0.2, .6))
    c.text(c.cx, ny, shown, "bold", s.get("size", 300), "accent", prog(t, 0.2, .3), scale=punch(t, 1.3, 0.3, 0.05))
    q = prog(t, 1.3, .6)
    c.text(c.cx, c.Y(1120) if not c.wide else c.H * .72, c.fit(s.get("caption", ""), "bold", 54), "bold", 54, "fg", q, dy=(1 - q) * c.S(30))
    _source(c, s, t)


@scene("bars", fields={**_SRC, "title": (str, False), "items": (list, True), "note": (str, False)},
       cues=lambda s: [(0.4 + k * 0.35, "tick") for k in range(len(s.get("items", [])))],
       desc="Horizontal bars. items: {label, value, suffix?, decimals?, accent?}.")
def bars(c, t, s):
    items = s["items"]
    if not items: return
    mx = max(max(i["value"] for i in items), 1e-9); left = c.W * 0.08; bw = c.W * 0.62
    c.text(c.cx, c.H * 0.15, c.fit(s.get("title", ""), "bold", 62), "bold", 62, "fg", prog(t, 0.1, .5))
    y = c.H * 0.30; step = min(c.S(230), c.H * 0.6 / len(items))
    for k, it in enumerate(items):
        p = out_cubic(prog(t, 0.4 + k * 0.35, 0.9))
        c.text(left, y, it["label"], "mono", 36, "muted", p, anchor="la")
        w = bw * max(0.0, it["value"]) / mx * p
        c.rect((left, y + c.S(56), left + max(w, 6), y + c.S(126)), "accent" if it.get("accent") else "dim", radius=c.S(14))
        c.text(left + w + c.S(18), y + c.S(62), f'{it["value"] * p:,.{it.get("decimals", 1)}f}{it.get("suffix", "")}', "bold", 52, "fg", p, anchor="la")
        y += step
    c.text(c.cx, c.H * 0.82, c.fit(s.get("note", ""), "reg", 40, 0.8), "reg", 40, "muted", prog(t, 2.2, .5))
    _source(c, s, t)


@scene("chart", fields={**_SRC, "title": (str, False), "series": (list, True), "labels": (list, False), "note": (str, False),
                        "zero": (bool, False), "suffix": (str, False)},
       cues=lambda s: [(0.3, "whoosh")], desc="Animated line chart. series: [{label, values, accent?}], labels = x-axis labels.")
def chart(c, t, s):
    ser = [x for x in s["series"] if x.get("values")]
    if not ser: return
    n = max(len(x["values"]) for x in ser)
    allv = [v for x in ser for v in x["values"]]; lo = 0 if s.get("zero", True) else min(allv); hi = max(allv)
    if hi == lo: hi = lo + 1
    dec = _nice_decimals(lo, hi)
    x0, x1 = c.W * 0.12, c.W * 0.92; y0, y1 = c.H * (0.30 if not c.wide else 0.26), c.H * (0.66 if not c.wide else 0.78)
    c.text(c.cx, c.H * 0.15 if not c.wide else c.H * 0.1, c.fit(s.get("title", ""), "bold", 62), "bold", 62, "fg", prog(t, 0.1, .5))
    for g in range(5):
        gy = lerp(y1, y0, g / 4); c.line([(x0, gy), (x1, gy)], max(1, c.S(2)), "dim", 0.9)
        c.text(x0 - c.S(14), gy - c.S(18), f'{lerp(lo, hi, g / 4):,.{dec}f}', "mono", 26, "muted", 1, anchor="ra")
    labels = s.get("labels") or []
    for i, lb in enumerate(labels[:n]):
        c.text(lerp(x0, x1, i / max(1, n - 1)), y1 + c.S(18), str(lb), "mono", 26, "muted", prog(t, 0.2, .4))
    k = prog(t, 0.3, 1.8); k = in_out(k)
    for si, x in enumerate(ser):
        pts = [(lerp(x0, x1, i / max(1, n - 1)), lerp(y1, y0, (v - lo) / (hi - lo))) for i, v in enumerate(x["values"])]
        upto = k * (len(pts) - 1); i = int(upto); frac = upto - i; draw = pts[: i + 1]
        if i + 1 < len(pts): draw = draw + [(lerp(pts[i][0], pts[i + 1][0], frac), lerp(pts[i][1], pts[i + 1][1], frac))]
        col = "accent" if x.get("accent", si == 0) else "muted"
        c.line(draw, c.S(8), col)
        if draw: c.dot(draw[-1][0], draw[-1][1], c.S(14), col)
        if x.get("label"): c.text(pts[-1][0], pts[-1][1] - c.S(52), x["label"], "bold", 32, col, prog(t, 2.0, .4))
    c.text(c.cx, c.H * 0.82, c.fit(s.get("note", ""), "reg", 40, 0.8), "reg", 40, "muted", prog(t, 2.4, .5))
    _source(c, s, t)


@lru_cache(maxsize=64)
def _spread(total, hit):
    """Pick `hit` of `total` indices spread evenly (no clumps): rank cells by a low-discrepancy sequence, take the first `hit`."""
    rank = sorted(range(total), key=lambda i: (i * 0.6180339887) % 1.0)
    return tuple(sorted(rank[:hit]))


@scene("grid", fields={**_SRC, "total": (int, True), "hit": (int, True), "title": (str, False), "label_total": (str, False),
                       "label_hit": (str, False), "cols": (int, False)},
       cues=lambda s: [(0.2, "whoosh"), (2.0, "rise"), (3.6, "thud")],
       desc="Proportion grid: `total` dots, `hit` of them light up. Shows 'x of y' at a glance.")
def grid(c, t, s):
    total = max(1, min(int(s["total"]), 20000)); hit = max(0, min(int(s["hit"]), total)); wide = c.wide
    area_w, area_h = (c.W * 0.52, c.H * 0.7) if wide else (c.W * 0.86, c.H * 0.26)
    cols = s.get("cols") or max(1, min(total, round(math.sqrt(total * area_w / area_h))))
    rows = -(-total // cols); gap = min(area_w / cols, area_h / rows, c.S(64)); r = gap * 0.34
    gx0 = c.W * 0.06 + gap / 2 if wide else c.cx - (cols - 1) * gap / 2
    gy0 = (c.H * 0.5 - rows * gap / 2 + gap / 2) if wide else c.Y(740)
    order = _spread(total, hit); idx = {v: n for n, v in enumerate(order)}
    n_vis = int(total * in_out(prog(t, 0.2, 1.6))); lit_k = in_out(prog(t, 2.0, 1.6)); n_lit = int(hit * lit_k)
    for i in range(min(n_vis, total)):
        x, y = gx0 + (i % cols) * gap, gy0 + (i // cols) * gap
        if i in idx and idx[i] < n_lit:
            k = prog(t, 2.0 + idx[i] / max(1, hit) * 1.6, 0.25); c.dot(x, y, r + c.S(9) * (1 - k) + 1, "accent")
        else: c.dot(x, y, r, "dim", 1)
    tx = c.W * 0.78 if wide else c.cx; colw = 0.34 if wide else 0.86
    Y = (lambda tall, frac: c.H * frac) if wide else (lambda tall, frac: c.Y(tall))
    p0 = out_cubic(prog(t, 0.1, .5))
    c.text(tx, Y(280, .16), c.fit(s.get("title", ""), "bold", 62, colw), "bold", 62, "fg", p0, dy=(1 - p0) * c.S(40))
    c.text(tx, Y(440, .38), str(int(round(hit * lit_k))), "bold", 200, "accent", prog(t, 1.9, .3))
    c.text(tx, Y(630, .62), c.fit(f'{total:,} {s.get("label_total", "")}', "mono", 30, 0.3 if wide else 0.86), "mono", 30, "muted", prog(t, 0.2, .5))
    c.text(tx, Y(1290, .76), c.fit(s.get("label_hit", ""), "bold", 56, colw), "bold", 56, "fg", prog(t, 3.3, .5))
    _source(c, s, t)


@scene("compare", fields={**_SRC, "title": (str, False), "left": (dict, True), "right": (dict, True)},
       cues=lambda s: [(0.3, "whoosh"), (0.9, "tick")],
       desc="Two cards side by side (stacked on tall formats): before/after, us/them. left/right: {title, items[]}.")
def compare(c, t, s):
    c.text(c.cx, c.H * 0.12, c.fit(s.get("title", ""), "bold", 62), "bold", 62, "fg", prog(t, 0.1, .5))
    boxes = ([(c.W * 0.05, c.H * 0.24, c.W * 0.485, c.H * 0.9), (c.W * 0.515, c.H * 0.24, c.W * 0.95, c.H * 0.9)] if c.wide else
             [(c.W * 0.06, c.H * 0.2, c.W * 0.94, c.H * 0.5), (c.W * 0.06, c.H * 0.52, c.W * 0.94, c.H * 0.82)])
    for k, (key, tone) in enumerate((("left", "dim"), ("right", "accent"))):
        card = s[key]; p = out_cubic(prog(t, 0.3 + k * 0.4, 0.6)); b = boxes[k]
        p *= 1.0 if k else 1.0 - 0.45 * in_out(prog(t, 1.6, 0.5))      # the left card dims once the right one lands
        off = (1 - p) * c.S(80) * (-1 if k == 0 else 1)
        bx = (b[0] + (off if c.wide else 0), b[1] + (0 if c.wide else off), b[2] + (off if c.wide else 0), b[3] + (0 if c.wide else off)); c.shadow_rect(bx, c.S(30), c.S(28), 0.4 * p); c.rect(bx, "card", p, radius=c.S(30))
        c.rect((b[0], b[1], b[0] + c.S(14), b[3]), tone, p)
        x = b[0] + c.S(50); y = b[1] + c.S(36)
        c.text(x, y, card.get("title", ""), "bold", 52, "accent" if k else "muted", p, anchor="la")
        y += c.S(90)
        for j, it in enumerate(card.get("items", [])):
            q = out_cubic(prog(t, 0.8 + k * 0.4 + j * 0.3, 0.5)); w = b[2] - x - c.S(40)
            txt = c.wrap(it, "reg", c.S(40), w); c.text(x, y, txt, "reg", 40, "fg", q, anchor="la"); y += c.S(60) * (1 + txt.count("\n")) + c.S(14)


@scene("timeline", fields={**_SRC, "title": (str, False), "events": (list, True)},
       cues=lambda s: [(0.4 + k * 0.5, "tick") for k in range(len(s.get("events", [])))],
       desc="Milestones along a line. events: {when, what}. Horizontal on wide formats, vertical on tall.")
def timeline(c, t, s):
    ev = s["events"]; n = len(ev)
    if not n: return
    c.text(c.cx, c.H * 0.12, c.fit(s.get("title", ""), "bold", 62), "bold", 62, "fg", prog(t, 0.1, .5))
    if c.wide:
        y = c.H * 0.52; x0, x1 = c.W * 0.1, c.W * 0.9; c.line([(x0, y), (lerp(x0, x1, in_out(prog(t, 0.2, 0.4 + n * 0.5))), y)], c.S(6), "dim")
        for k, e in enumerate(ev):
            x = lerp(x0, x1, k / max(1, n - 1)); p = out_back(prog(t, 0.4 + k * 0.5, 0.5))
            c.dot(x, y, c.S(18) * p, "accent")
            c.text(x, y - c.S(100) if k % 2 == 0 else y + c.S(40), e["when"], "bold", 40, "accent", p)
            c.text(x, y - c.S(50) if k % 2 == 0 else y + c.S(90), c.wrap(e["what"], "reg", c.S(32), c.W * 0.7 / n), "reg", 32, "fg", p, anchor="ma")
    else:
        x = c.W * 0.2; y0, y1 = c.H * 0.24, c.H * 0.76
        c.line([(x, y0), (x, lerp(y0, y1, in_out(prog(t, 0.2, 0.4 + n * 0.5))))], c.S(6), "dim")
        for k, e in enumerate(ev):
            y = lerp(y0, y1, k / max(1, n - 1)) if n > 1 else y0; p = out_back(prog(t, 0.4 + k * 0.5, 0.5))
            c.dot(x, y, c.S(20) * p, "accent")
            c.text(x + c.S(60), y - c.S(30), e["when"], "bold", 42, "accent", p, anchor="la")
            c.text(x + c.S(60), y + c.S(24), c.wrap(e["what"], "reg", c.S(36), c.W * 0.62), "reg", 36, "fg", p, anchor="la")
