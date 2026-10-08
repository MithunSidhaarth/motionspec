"""Easing, springs and timing helpers. Easing functions map [0,1] -> [0,1] (overshoot allowed for back/elastic)."""
import math


def clamp(x, a=0.0, b=1.0): return a if x < a else b if x > b else x


def prog(t, t0, dur):
    """Progress of a window that starts at t0 and lasts dur seconds, clamped to [0,1]."""
    return clamp((t - t0) / dur) if dur > 0 else float(t >= t0)


def lerp(a, b, x): return a + (b - a) * x
def linear(x): return x
def in_quad(x): return x * x
def out_quad(x): return 1 - (1 - x) ** 2
def in_cubic(x): return x ** 3
def out_cubic(x): return 1 - (1 - x) ** 3
def in_out(x): return x * x * (3 - 2 * x)
def in_out_cubic(x): return 4 * x ** 3 if x < .5 else 1 - (-2 * x + 2) ** 3 / 2
def out_expo(x): return 1.0 if x >= 1 else 1 - 2 ** (-10 * x)


def in_out_expo(x):
    if x <= 0: return 0.0
    if x >= 1: return 1.0
    return 2 ** (20 * x - 10) / 2 if x < .5 else (2 - 2 ** (-20 * x + 10)) / 2


def out_back(x, s=1.7):
    x -= 1
    return 1 + (s + 1) * x ** 3 + s * x ** 2


def out_elastic(x):
    if x <= 0: return 0.0
    if x >= 1: return 1.0
    return 2 ** (-10 * x) * math.sin((x * 10 - 0.75) * (2 * math.pi) / 3) + 1


def out_bounce(x):
    n, d = 7.5625, 2.75
    if x < 1 / d: return n * x * x
    if x < 2 / d: x -= 1.5 / d; return n * x * x + .75
    if x < 2.5 / d: x -= 2.25 / d; return n * x * x + .9375
    x -= 2.625 / d
    return n * x * x + .984375


def spring(x, zeta=0.55, cycles=2.5):
    """Damped spring step response sampled at x in [0,1]. Starts at 0, settles to 1; lower zeta = more bounce."""
    if x <= 0: return 0.0
    if x >= 1: return 1.0
    w = 2 * math.pi * cycles; d = math.sqrt(max(1e-6, 1 - zeta * zeta))
    decay = math.exp(-zeta * w * x * 0.5)
    return 1 - decay * (math.cos(d * w * x * 0.5) + zeta / d * math.sin(d * w * x * 0.5))


def bezier(x1, y1, x2, y2):
    """CSS/After-Effects style cubic-bezier easing. Returns f(x)."""
    def f(x):
        if x <= 0: return 0.0
        if x >= 1: return 1.0
        lo, hi = 0.0, 1.0
        for _ in range(24):
            mid = (lo + hi) / 2
            bx = 3 * (1 - mid) ** 2 * mid * x1 + 3 * (1 - mid) * mid ** 2 * x2 + mid ** 3
            lo, hi = (mid, hi) if bx < x else (lo, mid)
        m = (lo + hi) / 2
        return 3 * (1 - m) ** 2 * m * y1 + 3 * (1 - m) * m ** 2 * y2 + m ** 3
    return f


def punch(t, t0, dur=0.25, amount=0.08):
    """Scale multiplier for a short pulse at t0: 1 -> 1+amount -> 1."""
    k = prog(t, t0, dur)
    return 1 + amount * math.sin(k * math.pi) if 0 < k < 1 else 1.0


def drift(t, seed=0.0, speed=0.35):
    """Smooth pseudo-noise in [-1,1] for gentle camera movement (sum of sines; deterministic)."""
    return (math.sin(t * speed * 2.1 + seed) + 0.5 * math.sin(t * speed * 3.7 + seed * 1.7)) / 1.5


EASINGS = {n: f for n, f in (
    ("linear", linear), ("in_quad", in_quad), ("out_quad", out_quad), ("in_cubic", in_cubic), ("out_cubic", out_cubic),
    ("in_out", in_out), ("in_out_cubic", in_out_cubic), ("out_expo", out_expo), ("in_out_expo", in_out_expo),
    ("out_back", out_back), ("out_elastic", out_elastic), ("out_bounce", out_bounce), ("spring", spring))}


def get_ease(name_or_fn):
    """Look up an easing by name (so JSON specs can say "ease": "spring")."""
    if callable(name_or_fn): return name_or_fn
    if name_or_fn not in EASINGS: raise ValueError(f"unknown easing '{name_or_fn}'. Choose from {sorted(EASINGS)}")
    return EASINGS[name_or_fn]


def stagger(t, i, start=0.15, step=0.2, dur=0.55, ease=out_cubic, n=None, order="forward", jitter=0.0):
    """Eased progress of the i-th of n items in a staggered reveal. order: forward | reverse | center."""
    if order == "reverse" and n: i = n - 1 - i
    elif order == "center" and n: i = abs(i - (n - 1) / 2) * 2
    j = ((math.sin(i * 12.9898) * 43758.5453) % 1.0) * jitter
    return get_ease(ease)(prog(t, start + i * step + j, dur))


def count_up(t, t0, dur, value, ease=in_out):
    return value * get_ease(ease)(prog(t, t0, dur))
