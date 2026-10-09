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


def _key():
    n = int(0.035 * SR); x = np.arange(n) / SR; rng = np.random.default_rng(5)
    return (0.35 * rng.standard_normal(n) * _env(n, 14) + 0.4 * np.sin(2 * np.pi * 1700 * x) * _env(n, 18))


def _click():
    n = int(0.02 * SR); return 0.6 * np.sin(2 * np.pi * 3600 * np.arange(n) / SR) * _env(n, 16)


def _chime():
    n = int(0.9 * SR); x = np.arange(n) / SR
    return 0.3 * (np.sin(2 * np.pi * 880 * x) + 0.5 * np.sin(2 * np.pi * 1320 * x) + 0.25 * np.sin(2 * np.pi * 1760 * x)) * _env(n, 4.5)


def _impact():
    n = int(0.7 * SR); x = np.arange(n) / SR; rng = np.random.default_rng(9)
    boom = np.sin(2 * np.pi * (48 + 60 * np.exp(-x * 14)) * x) * _env(n, 5)
    crack = rng.standard_normal(n) * np.exp(-x * 60) * 0.35
    return 0.95 * boom + crack


def _swish():
    n = int(0.28 * SR); noise = np.random.default_rng(3).standard_normal(n); c = np.cumsum(noise)
    k = np.linspace(40, 6, n).astype(int); idx = np.arange(n); sw = (c[idx] - c[np.maximum(0, idx - k)]) / k
    sw /= (np.abs(sw).max() + 1e-9); return 0.5 * sw * np.sin(np.linspace(0, np.pi, n)) ** 1.5


def _stamp():
    n = int(0.4 * SR); x = np.arange(n) / SR
    return 0.9 * np.sin(2 * np.pi * (90 + 120 * np.exp(-x * 40)) * x) * _env(n, 11) + 0.25 * _click().mean() * np.zeros(n)


def _riser():
    n = int(1.4 * SR); x = np.arange(n) / SR; noise = np.random.default_rng(2).standard_normal(n)
    f = 200 + 1800 * (x / x[-1]) ** 2.2
    return 0.22 * np.sin(2 * np.pi * np.cumsum(f) / SR) * (x / x[-1]) ** 1.5 + 0.12 * noise * (x / x[-1]) ** 3


def _success():
    n = int(0.5 * SR); x = np.arange(n) / SR; a = np.where(x < 0.12, np.sin(2 * np.pi * 660 * x), np.sin(2 * np.pi * 990 * x))
    return 0.35 * a * _env(n, 6)


SOUNDS = {"tick": _tick, "pop": _pop, "whoosh": _whoosh, "rise": _rise, "thud": _thud, "key": _key, "click": _click, "chime": _chime,
          "impact": _impact, "swish": _swish, "stamp": _stamp, "riser": _riser, "success": _success}
_CACHE = {}


def _sound(name):
    if name not in _CACHE: _CACHE[name] = SOUNDS[name]()
    return _CACHE[name]


def _smooth_gate(v, thresh=0.02, hold=0.25):
    win = int(0.05 * SR); env = np.convolve(np.abs(v), np.ones(win) / win, mode="same")
    h = int(hold * SR); return np.clip(np.convolve((env > thresh).astype(np.float32), np.ones(h) / h, mode="same") * 3, 0, 1)


def mix(cues, duration, out_wav, voiceover=None, music=None, sfx_db=-16.0, duck_db=-10.0, music_db=-22.0, voice_segments=None):
    """Write a mono 16-bit wav of exactly `duration` seconds. `music` is a path or {"src", "db"}; it ducks under speech."""
    n = int(round(duration * SR)); out = np.zeros(n, np.float64)
    sfx = np.zeros(n, np.float64)
    for cue in cues:
        t, name = cue[0], cue[1]; gain = 10 ** ((cue[2] if len(cue) > 2 else 0) / 20)          # optional third item: gain in dB
        if name not in SOUNDS: raise ValueError(f"unknown sound cue '{name}' (available: {sorted(SOUNDS)})")
        i = int(round(t * SR)); s = _sound(name)
        if 0 <= i < n: sfx[i:i + len(s)] += s[: n - i] * gain
    sfx *= 10 ** (sfx_db / 20)
    voice = np.zeros(n)
    if voiceover and voice_segments:                       # narration clips placed at their scene starts (scenes without speech stay silent)
        full = decode(voiceover, int((max(a1 for _, a1, _ in voice_segments) + 1) * SR))
        for a0, a1, v0 in voice_segments:
            seg = full[int(a0 * SR): int(a1 * SR)]; i = int(round(v0 * SR))
            if 0 <= i < n: voice[i:i + len(seg)] += seg[: n - i]
    elif voiceover:
        voice = decode(voiceover, n).astype(np.float64)
    gate = _smooth_gate(voice) if voiceover else np.zeros(n)
    duck = 1 - gate * (1 - 10 ** (duck_db / 20))
    out += sfx * duck
    if voiceover: out += voice
    if music:
        if isinstance(music, dict) and "mood" in music:                      # generated by motionspec.music (original, licence-free)
            from .music import generate
            db = music.get("db", -4.0); m = generate(duration, music["mood"], music.get("seed", "motionspec")).astype(np.float64)[:n]
            m = np.pad(m, (0, n - len(m))) * 10 ** (db / 20)
        else:
            src, db = (music, music_db) if isinstance(music, str) else (music["src"], music.get("db", music_db))
            m = decode(src, n).astype(np.float64) * 10 ** (db / 20); fade = int(1.0 * SR)
            m[:fade] *= np.linspace(0, 1, fade); m[-fade:] *= np.linspace(1, 0, fade)
        out += m * duck
    peak = np.abs(out).max()
    if peak > 0.95: out *= 0.95 / peak
    with wave.open(out_wav, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((out * 32767).astype(np.int16).tobytes())
    return out_wav
