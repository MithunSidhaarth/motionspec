"""Policy: project-specific content rules as data, so the same engine can enforce different standards per project.

policy.json example:
{
  "banned": ["guaranteed", "best in the world"],          # whole-word, case-insensitive, checked in every on-screen string
  "required_any": ["not proof", "screening indicator"],   # at least one must appear on screen
  "facts_file": "facts.json",                             # numbers on screen must appear in the cited facts;
                                                          # a fact with "restricted": true also needs spec.approved_facts
  "numbers_free_below": 10,                               # small counters (steps, list indexes) need no source
  "kinds": {"reel": [15, 45], "ad": [6, 30]},             # allowed length per spec.kind
  "max_caption_words": 9, "hook_max_seconds": 3.5, "require_last": "endcard"
}
"""
import json
import os
import re

SKIP_KEYS = {"type", "dur", "bg", "gradient", "cols", "size", "decimals", "id", "camera", "transition", "comment", "src", "step", "zoom", "zoom_dur",
             "pan", "fit", "loop", "start", "cps", "highlight", "accent", "hold", "invert", "numbered", "zero", "commas"}
DEFAULT_KINDS = {"reel": (15, 45), "ad": (6, 30), "explainer": (30, 240), "demo": (20, 120), "general": (3, 600)}


def screen_strings(spec):
    """Every string/number that will be visible on screen, scene by scene: [(label, text)]."""
    out = []
    def walk(v, label):
        if isinstance(v, str): out.append((label, v))
        elif isinstance(v, bool): pass
        elif isinstance(v, (int, float)): out.append((label, str(v)))
        elif isinstance(v, list): [walk(x, label) for x in v]
        elif isinstance(v, dict): [walk(x, label) for k, x in v.items() if k not in SKIP_KEYS]
    for i, sc in enumerate(spec.get("scenes", [])):
        for k, v in sc.items():
            if k not in SKIP_KEYS: walk(v, f"scenes[{i}].{k}")
    for j, c in enumerate(spec.get("captions", [])): out.append((f"captions[{j}]", c.get("text", "")))
    return out


def lint(spec, policy=None, base_dir="."):
    """Returns (errors, warnings). With no policy only structural checks run."""
    p = policy or {}; errs, warns = [], []
    strings = screen_strings(spec); blob = " ".join(s for _, s in strings); low = blob.lower()
    for w in p.get("banned", []):
        for label, s in strings:
            if re.search(r"\b" + re.escape(w.lower()), s.lower()): errs.append(f"{label}: banned word/phrase '{w}'")
    if p.get("required_any") and not any(r.lower() in low for r in p["required_any"]):
        errs.append(f"on-screen text must include one of: {p['required_any']}")
    if p.get("facts_file"):
        fp = p["facts_file"] if os.path.isabs(p["facts_file"]) else os.path.join(base_dir, p["facts_file"])
        with open(fp, encoding="utf-8") as fh: facts = {f["id"]: f for f in json.load(fh)["facts"]}
        used = spec.get("facts", [])
        allowed = {str(i) for i in range(0, int(p.get("numbers_free_below", 10)) + 1)}
        for f in used:
            if f not in facts: errs.append(f"facts: unknown id '{f}'")
            else:
                allowed |= {str(x) for x in facts[f].get("numbers", [])}
                if facts[f].get("restricted") and f not in spec.get("approved_facts", []):
                    errs.append(f"facts: '{f}' is restricted ({facts[f].get('why', 'needs sign-off')}); add it to \"approved_facts\" only after review")
        for label, s in strings:
            for n in re.findall(r"\d[\d,\.]*\d|\d", s):
                n = n.rstrip(".,")
                if n not in allowed: errs.append(f"{label}: number '{n}' is not in the cited facts ({', '.join(used) or 'none cited'})")
    dur = sum(s["dur"] for s in spec.get("scenes", [])); kind = spec.get("kind", "general")
    lo, hi = {**DEFAULT_KINDS, **{k: tuple(v) for k, v in p.get("kinds", {}).items()}}.get(kind, (3, 600))
    if not lo <= dur <= hi: warns.append(f"length {dur:.0f}s is outside {lo}-{hi}s for kind '{kind}'")
    sc = spec.get("scenes", [])
    if sc and kind in ("reel", "ad") and sc[0]["dur"] > p.get("hook_max_seconds", 3.5): warns.append(f"first scene is {sc[0]['dur']}s; hooks should land within {p.get('hook_max_seconds', 3.5)}s")
    if sc and p.get("require_last") and sc[-1]["type"] != p["require_last"]: warns.append(f"last scene should be '{p['require_last']}'")
    for c in spec.get("captions", []):
        if len(str(c.get("text", "")).split()) > p.get("max_caption_words", 9): warns.append(f"caption too long: '{c['text']}'")
    return errs, warns


def load_policy(path):
    if not path: return None
    with open(path, encoding="utf-8") as fh: return json.load(fh)
