"""Word-level alignment of a script to a voiceover, with no mandatory model download.

Engine 1 (always available): ffmpeg `silencedetect` finds the speech segments; script words are spread across them in order,
weighted by word length (longer words take longer to say). Accuracy is good to roughly 100-150 ms on natural speech.
Engine 2 (optional): if `faster-whisper` is installed (`pip install faster-whisper`), real word timestamps are used and
matched to the script, which is accurate to tens of milliseconds. Select with align engine "auto" (default), "heuristic" or "whisper".
"""
import re
import subprocess

from .audio import probe_duration


def speech_segments(path, noise_db=-34, min_pause=0.18):
    """[(start, end)] of speech, the inverse of the silences."""
    total = probe_duration(path)
    r = subprocess.run(["ffmpeg", "-v", "info", "-protocol_whitelist", "file", "-i", path, "-af", f"silencedetect=noise={noise_db}dB:d={min_pause}",
                        "-f", "null", "-"], capture_output=True, text=True, timeout=300)
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.\-e]+)", r.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r.stderr)]
    segs, cur = [], 0.0
    for i, s in enumerate(starts):
        if s - cur > 0.05: segs.append((cur, max(cur + 0.05, s)))
        cur = ends[i] if i < len(ends) else total
    if total - cur > 0.05: segs.append((cur, total))
    return segs or [(0.0, total)]


def _weight(w): return len(re.sub(r"\W", "", w)) + 2.0


def _sentence_sizes(words):
    sizes, n = [], 0
    for w in words:
        n += 1
        if re.search(r"[.!?]$", w): sizes.append(n); n = 0
    if n: sizes.append(n)
    return sizes


def heuristic(path, words):
    """Place `words` on the audio. If the script has as many sentences as the audio has speech segments, each sentence snaps to
    its own segment (words weighted by length inside it); otherwise words are spread over all speech, weighted by length."""
    segs = speech_segments(path); sizes = _sentence_sizes(words)
    if len(sizes) == len(segs) and len(segs) > 1:
        out, i = [], 0
        for (a, b), n in zip(segs, sizes):
            chunk = words[i:i + n]; tw = sum(_weight(w) for w in chunk) or 1.0; t = a
            for w in chunk:
                d = (b - a) * _weight(w) / tw; out.append({"word": w, "t0": round(t, 3), "t1": round(t + d, 3)}); t += d
            i += n
        return out
    return _spread_all(segs, words)


def _spread_all(segs, words):
    total_w = sum(_weight(w) for w in words) or 1.0; speech = sum(e - s for s, e in segs)
    out, si, seg_left, t = [], 0, segs[0][1] - segs[0][0], segs[0][0]
    for w in words:
        need = _weight(w) / total_w * speech
        t0 = t; remaining = need
        while remaining > seg_left + 1e-9 and si + 1 < len(segs):         # word spans a pause: jump to the next speech segment
            remaining -= seg_left; si += 1; t = segs[si][0]; seg_left = segs[si][1] - segs[si][0]
        t += remaining; seg_left -= remaining
        out.append({"word": w, "t0": round(t0, 3), "t1": round(t, 3)})
        if seg_left < 1e-6 and si + 1 < len(segs): si += 1; t = segs[si][0]; seg_left = segs[si][1] - segs[si][0]
    return out


def whisper_words(path, words):
    """Real word timestamps via faster-whisper, matched to the script by position. Raises ImportError if not installed."""
    from faster_whisper import WhisperModel                      # optional dependency
    model = WhisperModel("base", device="cpu", compute_type="int8")
    heard = [w for seg in model.transcribe(path, word_timestamps=True)[0] for w in seg.words]
    if abs(len(heard) - len(words)) > max(2, len(words) // 5): raise ValueError("transcript does not match the script closely enough")
    out = []
    for i, w in enumerate(words):
        h = heard[min(i * len(heard) // max(1, len(words)), len(heard) - 1)]
        out.append({"word": w, "t0": round(h.start, 3), "t1": round(h.end, 3)})
    return out


def align(path, words, engine="auto"):
    if engine in ("auto", "whisper"):
        try: return whisper_words(path, words)
        except (ImportError, ValueError):
            if engine == "whisper": raise
    return heuristic(path, words)


def scene_durations(words_by_scene, aligned, pad=0.4, tail=0.8):
    """Scene lengths so each cut lands just after its last spoken word. words_by_scene: [n_words per scene (0 = keep None)]."""
    i, edges, last_end = 0, [], 0.0
    for n in words_by_scene:
        if n: i += n; last_end = aligned[i - 1]["t1"]; edges.append(last_end + pad)
        else: edges.append(None)
    edges = [e if e is None else e for e in edges]
    if edges and edges[-1] is not None: edges[-1] += tail - pad
    return edges
