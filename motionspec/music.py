"""Generative background music. Every video gets an original, loop-free track written in code: no sample files, no licences.

A track is a chord progression played as soft detuned pads, a plucked bass, an arpeggio and (for livelier moods) light drums,
with the pads and arpeggio ducked by the kick and softened with a short reverb. Mood sets tempo, scale, density and drums;
the seed (the spec id by default) picks key and pattern variations, so different videos sound different but the same video
always sounds the same.
"""
import hashlib
import math

import numpy as np

SR = 48000

# chord = (root offset in semitones from the key, quality)
QUAL = {"min": (0, 3, 7, 10), "maj": (0, 4, 7, 11), "dom": (0, 4, 7, 10), "sus": (0, 5, 7, 10)}
MOODS = {
    "calm":   dict(bpm=84,  prog=[(0, "min"), (8, "maj"), (3, "maj"), (10, "dom")], arp=0.55, drums=0.0,  bass=0.8, pad=1.0, hat=0.0,  clap=0.0, bright=0.5),
    "warm":   dict(bpm=76,  prog=[(0, "maj"), (9, "min"), (5, "maj"), (7, "dom")],  arp=0.6,  drums=0.35, bass=0.9, pad=0.9, hat=0.4,  clap=0.0, bright=0.45),
    "upbeat": dict(bpm=112, prog=[(0, "maj"), (7, "dom"), (9, "min"), (5, "maj")],  arp=0.8,  drums=0.85, bass=1.0, pad=0.7, hat=0.8,  clap=0.7, bright=0.8),
    "tense":  dict(bpm=98,  prog=[(0, "min"), (0, "min"), (8, "maj"), (7, "dom")],  arp=0.5,  drums=0.5,  bass=1.0, pad=0.9, hat=0.5,  clap=0.0, bright=0.35),
    "minimal": dict(bpm=90, prog=[(0, "sus"), (5, "sus"), (3, "sus"), (7, "sus")],  arp=0.35, drums=0.0,  bass=0.5, pad=0.9, hat=0.0,  clap=0.0, bright=0.4),
}
KINDS = {"reel": "upbeat", "ad": "upbeat", "explainer": "calm", "demo": "warm", "general": "calm"}


def mood_for(kind): return KINDS.get(kind, "calm")


def _hz(midi): return 440.0 * 2 ** ((midi - 69) / 12)


def _rng(seed): return np.random.default_rng(int(hashlib.sha1(str(seed).encode()).hexdigest()[:8], 16))


def _lowpass(x, cutoff, kernel_ms=40):
    """One-pole style lowpass by convolving with a truncated exponential (cheap and good enough for pads)."""
    n = int(SR * kernel_ms / 1000); a = math.exp(-2 * math.pi * cutoff / SR)
    k = (1 - a) * a ** np.arange(n)
    return np.convolve(x, k)[: len(x)]


def _fft_conv(x, ir):
    n = len(x) + len(ir) - 1; size = 1 << (n - 1).bit_length()
    return np.fft.irfft(np.fft.rfft(x, size) * np.fft.rfft(ir, size), size)[: len(x)]


def _reverb(x, wet=0.25, decay=0.9, seed=1):
    ir_n = int(SR * 1.4); t = np.arange(ir_n) / SR
    ir = _rng(("rev", seed)).standard_normal(ir_n) * np.exp(-t / (decay * 0.45)); ir[:int(0.01 * SR)] *= np.linspace(0, 1, int(0.01 * SR))
    ir /= (np.sqrt((ir ** 2).sum()) + 1e-9)
    return x * (1 - wet) + _fft_conv(x, ir) * wet * 1.6


def _voice(freq, n, bright):
    """A soft detuned saw-ish voice: a few harmonics, two slightly detuned copies."""
    t = np.arange(n) / SR; out = np.zeros(n)
    for det in (-0.0035, 0.0035):
        f = freq * (1 + det)
        for h in range(1, 7): out += np.sin(2 * np.pi * f * h * t + h) * (bright ** (h - 1)) / h
    return out / 4


def _env(n, a, r):
    e = np.ones(n); na, nr = int(a * SR), int(r * SR)
    if na: e[:na] = np.linspace(0, 1, na) ** 2
    if nr and nr < n: e[-nr:] *= np.linspace(1, 0, nr) ** 1.5
    return e


def _kick(n_tail=0.28):
    n = int(n_tail * SR); t = np.arange(n) / SR
    return np.sin(2 * np.pi * np.cumsum(45 + 90 * np.exp(-t * 35)) / SR) * np.exp(-t * 11)


def _hat(seed):
    n = int(0.06 * SR); nz = _rng(("hat", seed)).standard_normal(n); hp = nz - _lowpass(nz, 4000, 2)
    return hp * np.exp(-np.arange(n) / SR * 70) * 0.5


def _clap(seed):
    n = int(0.18 * SR); nz = _rng(("clap", seed)).standard_normal(n); t = np.arange(n) / SR
    env = np.exp(-t * 28) + 0.6 * np.exp(-np.maximum(t - 0.012, 0) * 28) * (t > 0.012)
    return (nz - _lowpass(nz, 1200, 4)) * env * 0.4


def _add(buf, sig, at):
    i = int(at * SR)
    if i >= len(buf) or i < 0: return
    j = min(len(buf), i + len(sig)); buf[i:j] += sig[: j - i]


def generate(duration, mood="calm", seed="motionspec"):
    """Mono float array of exactly `duration` seconds, peak-limited to about -3 dBFS, RMS around -18 dBFS."""
    if mood not in MOODS: raise ValueError(f"unknown music mood '{mood}'. Choose from {sorted(MOODS)}")
    m = MOODS[mood]; rng = _rng(("music", seed, mood)); n = int(round(duration * SR)); tail = int(2 * SR)
    key = int(rng.choice([45, 47, 48, 50, 52, 53, 55]))                   # A2 .. G3 range: root of the bass register
    beat = 60.0 / m["bpm"]; bar = 4 * beat; bars = int(math.ceil(duration / bar)) + 1
    pads, arp, bass, drums = (np.zeros(n + tail) for _ in range(4)); kicks = []
    variation = int(rng.integers(0, 3))                                 # which arpeggio pattern this seed uses
    patterns = [(0, 1, 2, 3, 2, 1, 2, 1), (0, 2, 1, 3, 2, 1, 3, 2), (3, 2, 1, 0, 1, 2, 3, 2)]
    for b in range(bars):
        t0 = b * bar; root_off, q = m["prog"][b % len(m["prog"])]; tones = [key + 12 + root_off + s for s in QUAL[q]]
        nb = int(bar * SR) + int(0.6 * SR)
        pad = sum(_voice(_hz(x), nb, m["bright"]) for x in tones[:3] + [tones[0] + 12]) * _env(nb, 0.5, 0.9)
        _add(pads, _lowpass(pad, 1400 + 2800 * m["bright"]) * m["pad"] * 0.55, t0)
        bn = key + root_off - 12 + 12
        for k, off in enumerate((0, 2) if m["drums"] < 0.5 else (0, 1.5, 2, 3.5)):                      # bass hits
            ln = int(0.5 * SR); tt = np.arange(ln) / SR
            _add(bass, np.sin(2 * np.pi * _hz(bn) * tt) * np.exp(-tt * 5) * 0.5 * m["bass"], t0 + off * beat)
        pat = patterns[variation]
        for s in range(8):                                                                       # eighth-note arpeggio
            ln = int(0.32 * SR); tt = np.arange(ln) / SR; f = _hz(tones[pat[s] % len(tones)] + 12)
            vel = (0.9 if s % 4 == 0 else 0.6) * m["arp"] * (0.7 + 0.3 * rng.random())
            if rng.random() < 0.1 and m["drums"] < 0.5: continue                                  # occasional rest keeps it human
            _add(arp, (np.sin(2 * np.pi * f * tt) + 0.4 * np.sin(2 * np.pi * 2 * f * tt)) * np.exp(-tt * 9) * 0.22 * vel, t0 + s * beat / 2)
        if m["drums"]:
            for k in (0, 2):
                kicks.append(t0 + k * beat); _add(drums, _kick() * 0.9 * m["drums"], t0 + k * beat)
            if m["drums"] > 0.7: kicks.append(t0 + 3.5 * beat); _add(drums, _kick() * 0.6 * m["drums"], t0 + 3.5 * beat)
            for s in range(8):
                if s % 2 == 1 and m["hat"]: _add(drums, _hat((seed, b, s)) * m["hat"], t0 + s * beat / 2)
            if m["clap"]:
                for k in (1, 3): _add(drums, _clap((seed, b, k)) * m["clap"], t0 + k * beat)
    bus = _reverb(pads + arp, wet=0.28, seed=seed)
    if kicks:                                                                                   # sidechain: pads and arp dip on each kick
        duck = np.ones(n + tail)
        for kt in kicks:
            i = int(kt * SR); ln = int(0.22 * SR)
            if i < len(duck): seg = 1 - 0.45 * np.exp(-np.arange(min(ln, len(duck) - i)) / SR * 14); duck[i:i + len(seg)] = np.minimum(duck[i:i + len(seg)], seg)
        bus = bus * duck
    mix = (bus + bass * 0.9 + drums)[:n]
    fi, fo = int(0.6 * SR), int(min(2.0, duration * 0.3) * SR)
    mix[:fi] *= np.linspace(0, 1, fi) ** 2; mix[-fo:] *= np.linspace(1, 0, fo) ** 1.5
    rms = math.sqrt(float((mix ** 2).mean()) + 1e-12); mix *= (10 ** (-18 / 20)) / rms
    peak = float(np.abs(mix).max())
    if peak > 0.7: mix *= 0.7 / peak
    return mix.astype(np.float32)
