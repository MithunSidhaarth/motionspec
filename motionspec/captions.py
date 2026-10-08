"""Captions: build timed captions from each scene's `say` text, merge with explicit ones, export SRT."""


def build(scenes, explicit=None, max_words=7, lead=0.25, tail=0.25):
    """Split every scene's `say` into chunks of at most `max_words`, spread evenly over the scene. Returns [{t0, t1, text}]."""
    caps, t = list(explicit or []), 0.0
    for sc in scenes:
        words = str(sc.get("say", "")).split(); d = sc["dur"]
        if words:
            chunks = [words[i:i + max_words] for i in range(0, len(words), max_words)]
            span = max(0.5, d - lead - tail); total = sum(len(c) for c in chunks); at = t + lead
            for c in chunks:
                dur = span * len(c) / total; caps.append({"t0": round(at, 3), "t1": round(at + dur, 3), "text": " ".join(c)}); at += dur
        t += d
    return sorted(caps, key=lambda c: c["t0"])


def _ts(x):
    h, rem = divmod(int(round(x * 1000)), 3600000); m, rem = divmod(rem, 60000); s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def to_srt(caps):
    return "\n".join(f"{i}\n{_ts(c['t0'])} --> {_ts(c['t1'])}\n{c['text']}\n" for i, c in enumerate(caps, 1))
