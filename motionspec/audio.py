"""Audio: synthesised cue sounds placed at sample offsets, optional voiceover and music bed with ducking, loudness at mux time.
Duration always comes from the timeline (and is checked against the voiceover), so picture and sound cannot drift."""
import json
import subprocess
import wave

import numpy as np

SR = 48000


def probe_duration(path):
    """Seconds, via ffprobe. Raises RuntimeError with a doctor hint if ffprobe is missing or the file is unreadable."""
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", path],
                             capture_output=True, check=True, timeout=60).stdout
        return float(json.loads(out)["format"]["duration"])
    except (FileNotFoundError, subprocess.CalledProcessError, KeyError, ValueError, subprocess.TimeoutExpired) as e:
        raise RuntimeError(f"cannot read audio '{path}' ({type(e).__name__}). Is ffprobe installed? Run `motionspec doctor`.") from None


def decode(path, n):
    """Decode any audio file to mono float32 at SR, trimmed or zero-padded to n samples."""
    try:
        raw = subprocess.run(["ffmpeg", "-v", "error", "-protocol_whitelist", "file", "-i", path, "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"],
                             capture_output=True, check=True, timeout=600).stdout
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        raise RuntimeError(f"cannot decode audio '{path}' ({type(e).__name__}). Run `motionspec doctor`.") from None
    v = np.frombuffer(raw, dtype=np.float32)
    return v[:n] if len(v) >= n else np.pad(v, (0, n - len(v)))


def _env(n, k=9.0):
    x = np.arange(n) / SR; e = np.exp(-k * x / (n / SR)); a = int(0.002 * SR); e[:a] *= np.linspace(0, 1, a); return e


def _tick():
    n = int(0.05 * SR); return 0.5 * np.sin(2 * np.pi * 2400 * np.arange(n) / SR) * _env(n, 7)


def _pop():
    n = int(0.09 * SR); x = np.arange(n) / SR; return 0.55 * np.sin(2 * np.pi * (500 + 900 * np.exp(-x * 60)) * x) * _env(n, 6)


def _whoosh():
    n = int(0.55 * SR); noise = np.random.default_rng(7).standard_normal(n); c = np.cumsum(noise)
    k = np.linspace(8, 90, n).astype(int); idx = np.arange(n)
    sw = (c[idx] - c[np.maximum(0, idx - k)]) / k; sw /= (np.abs(sw).max() + 1e-9)
    return 0.55 * sw * np.sin(np.linspace(0, np.pi, n)) ** 2


def _rise():
    n = int(0.7 * SR); x = np.arange(n) / SR; f = 300 + 700 * (x / x[-1]) ** 2
    return 0.32 * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.linspace(0, np.pi, n)) ** 1.5


def _thud():
    n = int(0.35 * SR); x = np.arange(n) / SR; return 0.9 * np.sin(2 * np.pi * (55 + 40 * np.exp(-x * 25)) * x) * _env(n, 8)


SOUNDS = {"tick": _tick, "pop": _pop, "whoosh": _whoosh, "rise": _rise, "thud": _thud}
_CACHE = {}


def _sound(name):
    if name not in _CACHE: _CACHE[name] = SOUNDS[name]()
    return _CACHE[name]


def _smooth_gate(v, thresh=0.02, hold=0.25):
    win = int(0.05 * SR); env = np.convolve(np.abs(v), np.ones(win) / win, mode="same")
    h = int(hold * SR); return np.clip(np.convolve((env > thresh).astype(np.float32), np.ones(h) / h, mode="same") * 3, 0, 1)


def mix(cues, duration, out_wav, voiceover=None, music=None, sfx_db=-16.0, duck_db=-10.0, music_db=-22.0):
    """Write a mono 16-bit wav of exactly `duration` seconds. `music` is a path or {"src", "db"}; it ducks under speech."""
    n = int(round(duration * SR)); out = np.zeros(n, np.float64)
    sfx = np.zeros(n, np.float64)
    for t, name in cues:
        if name not in SOUNDS: raise ValueError(f"unknown sound cue '{name}' (available: {sorted(SOUNDS)})")
        i = int(round(t * SR)); s = _sound(name)
        if 0 <= i < n: sfx[i:i + len(s)] += s[: n - i]
    sfx *= 10 ** (sfx_db / 20)
    gate = _smooth_gate(decode(voiceover, n)) if voiceover else np.zeros(n)
    duck = 1 - gate * (1 - 10 ** (duck_db / 20))
    out += sfx * duck
    if voiceover: out += decode(voiceover, n)
    if music:
        src, db = (music, music_db) if isinstance(music, str) else (music["src"], music.get("db", music_db))
        m = decode(src, n).astype(np.float64) * 10 ** (db / 20); fade = int(1.0 * SR)
        m[:fade] *= np.linspace(0, 1, fade); m[-fade:] *= np.linspace(1, 0, fade); out += m * duck
    peak = np.abs(out).max()
    if peak > 0.95: out *= 0.95 / peak
    with wave.open(out_wav, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((out * 32767).astype(np.int16).tobytes())
    return out_wav
