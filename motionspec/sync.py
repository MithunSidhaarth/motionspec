"""Word-sync helpers for scenes. When a scene has narration, the engine adds `_words` (spoken words with times relative to the scene
start). Scenes use these helpers to make things happen on the word that names them; with no narration they fall back to fixed timing."""
import re


def norm(w): return re.sub(r"\W", "", str(w).lower())


def find(s, key, default=None, after=0.0):
    """Local time (seconds into the scene) when a spoken word starting with `key` begins, at or after `after`; else `default`."""
    k = norm(key)
    if not k: return default
    for w in s.get("_words", []):
        if w["t0"] >= after - 1e-6 and norm(w["word"]).startswith(k): return w["t0"]
    return default


def sequence(s, texts, fallback_start=0.45, fallback_step=0.45):
    """One time per text, in order: the first spoken word of each text that appears (in order) in the narration, else a fixed beat.
    Matching tries each word of the text, so 'Writes the video spec' finds 'writes' or 'spec' wherever the speaker says it."""
    out, cursor = [], 0.0
    for k, text in enumerate(texts):
        t = None
        for tok in str(text).replace("*", "").split():
            if len(norm(tok)) < 4: continue                           # skip 'the', 'is', 'it'
            t = find(s, tok, None, cursor)
            if t is not None: break
        if t is None: t = fallback_start + k * fallback_step if not s.get("_words") else (out[-1] + 0.5 if out else fallback_start)
        out.append(t); cursor = t + 0.01
    return out
