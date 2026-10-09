"""Visual verbs: scenes that show an idea instead of listing it. flow (a process with things moving through it)."""
import math

from .. import sync
from ..ease import in_out, lerp, out_back, out_cubic, prog, punch
from . import scene


def _node_times(s):
    return sync.sequence(s, s.get("nodes", []), 0.5, 0.55)


@scene("flow", fields={"title": (str, False), "nodes": (list, True), "loop": (bool, False), "caption": (str, False)},
       cues=lambda s: [(0.1, "swish", -9)] + [(t, "pop") for t in _node_times(s)] + [(t - 0.2, "whoosh", -12) for t in _node_times(s)[1:]],
       desc="A process as nodes joined by arrows, with packets travelling through it. `nodes`: list of labels (each appears on its spoken word). Use for pipelines, workflows, 'then it does X'.")
def flow(c, t, s):
    nodes = [str(n) for n in s["nodes"]]; n = len(nodes)
    if not n: return
    times = _node_times(s)
    if s.get("title"): c.text(c.cx, c.H * 0.14, c.fit(s["title"], "bold", 64, 0.86), "bold", 64, "fg", out_cubic(prog(t, 0.1, .5)))
    horiz = c.wide
    w = c.W * 0.78 if horiz else c.W * 0.7; bw = min(c.S(300), (c.W * 0.84) / n - c.S(60)) if horiz else c.S(560); bh = c.S(130)
    pts = []
    for k in range(n):
        if horiz: pts.append((c.W * 0.11 + bw / 2 + k * ((c.W * 0.78 - bw) / max(1, n - 1)), c.H * 0.5))
        else: pts.append((c.cx, c.H * 0.26 + k * (c.H * 0.48 / max(1, n - 1))))
    last_done = times[-1] + 0.6
    for k in range(n - 1):                                       # arrows first so cards sit on top
        (x0, y0), (x1, y1) = pts[k], pts[k + 1]; a = in_out(prog(t, times[k + 1] - 0.35, 0.4))
        sx, sy = (x0 + bw / 2, y0) if horiz else (x0, y0 + bh / 2); ex, ey = (x1 - bw / 2, y1) if horiz else (x1, y1 - bh / 2)
        c.line([(sx, sy), (lerp(sx, ex, a), lerp(sy, ey, a))], max(2, c.S(6)), "dim")
        if a > 0.98:
            ang = math.atan2(ey - sy, ex - sx); hs = c.S(18)
            c.line([(ex - hs * math.cos(ang - 0.5), ey - hs * math.sin(ang - 0.5)), (ex, ey), (ex - hs * math.cos(ang + 0.5), ey - hs * math.sin(ang + 0.5))], max(2, c.S(6)), "muted")
        if t > last_done:                                         # packets travel the finished line, one per arrow, staggered
            ph = ((t - last_done) * 0.55 + k * 0.23) % 1.0
            px, py = lerp(sx, ex, ph), lerp(sy, ey, ph); c.glow(px, py, c.S(46), "accent", 0.35); c.dot(px, py, c.S(15), "accent", 1 - abs(ph - 0.5) * 0.5)
    for k, label in enumerate(nodes):
        p = out_back(prog(t, times[k], 0.5)); x, y = pts[k]; hot = (k == n - 1)
        y += math.sin(t * 2.2 + k * 1.1) * c.S(7) * min(1, max(0.0, t - times[k] - 0.5))          # settled nodes bob gently
        if p <= 0: continue
        wbox, hbox = bw * min(1, p), bh * min(1, p)
        c.shadow_rect((x - wbox / 2, y - hbox / 2, x + wbox / 2, y + hbox / 2), c.S(28), c.S(24), 0.45 * min(1, p))
        c.rect((x - wbox / 2, y - hbox / 2, x + wbox / 2, y + hbox / 2), "accent" if hot else "card", min(1, p), radius=c.S(28))
        c.text(x, y - c.S(26), c.wrap(label, "bold", c.S(40), bw - c.S(40)), "bold", 40, "accent_text" if hot else "fg", min(1, p * 2))
    if s.get("caption"): c.text(c.cx, c.H * 0.86, c.fit(s["caption"], "reg", 40, 0.8), "reg", 40, "muted", prog(t, last_done, .5))
