"""Autotime: snap scene durations to the pauses in a voiceover so picture follows speech, with no model download.
Uses ffmpeg `silencedetect`; picks the (n_scenes - 1) longest pauses as cut points."""
import re
import subprocess

from .audio import probe_duration


def pauses(path, noise_db=-32, min_len=0.22):
    """[(start, end)] of silences in an audio file."""
    r = subprocess.run(["ffmpeg", "-v", "info", "-protocol_whitelist", "file", "-i", path, "-af", f"silencedetect=noise={noise_db}dB:d={min_len}",
                        "-f", "null", "-"], capture_output=True, text=True, timeout=300)
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", r.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r.stderr)]
    return list(zip(starts, ends))


def durations(path, n_scenes, pad=0.35, min_scene=1.2):
    """Scene durations (seconds) that cut in the middle of the n_scenes-1 longest internal pauses, plus `pad` seconds of tail."""
    total = probe_duration(path)
    if n_scenes <= 1: return [round(total + pad, 2)]
    inner = [(s, e) for s, e in pauses(path) if 0.4 < s and e < total - 0.2]
    best = sorted(inner, key=lambda p: p[1] - p[0], reverse=True)[: n_scenes - 1]
    cuts = sorted((s + e) / 2 for s, e in best)
    if len(cuts) < n_scenes - 1:                       # not enough pauses: fall back to even splits for the remainder
        step = total / n_scenes; cuts = [step * (i + 1) for i in range(n_scenes - 1)]
    edges = [0.0, *cuts, total + pad]
    out = [max(min_scene, round(b - a, 2)) for a, b in zip(edges, edges[1:])]
    return out
