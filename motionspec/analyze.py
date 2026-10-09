"""Analyze: measure a spec the way a director would look at a cut, and say what to fix.

It renders the video at thumbnail size (fast) twice: once as it will ship, and once with the ambient layers off (camera drift,
backdrop, effects). The difference matters: pixels that move because a backdrop drifts do not make a video feel alive; things the
content does (words arriving, numbers rolling, shapes drawing) do. Reported:

  content motion   how much the scenes themselves change per second, and the longest stretch where nothing meaningful happens
  hook             how soon something happens, and how long the first scene lasts
  rhythm           cuts per minute and average scene length
  sound            sound cues per second (events with a sound) and whether music or narration is present
  variety          how many distinct kinds of scene are used
  legibility       text that does not fit the safe area
"""
import copy
import json

import numpy as np

from .render import Project, load_spec

TARGETS = {
    "cue_density": (3.0, "sound cues per second, 3 or more"),
    "still_stretch": (1.2, "longest stretch with no content change, 1.2 s or less"),
    "hook_motion": (0.6, "first content motion by 0.6 s"),
    "hook_scene": (3.6, "opening scene 3.6 s or shorter (ads and reels)"),
    "scene_mean": ((2.2, 6.5), "average scene length between 2.2 and 6.5 s"),
    "variety": (0.15, "distinct scene types per 10 seconds, 1.5 or more"),
}


def _small(spec_dict, base, fmt_name):
    from .layout import get_format
    f = get_format(fmt_name or spec_dict.get("format", "reel")); k = 320 / max(f.W, f.H)
    w, h = max(64, int(f.W * k) // 2 * 2), max(64, int(f.H * k) // 2 * 2)
    return f"{w}x{h}"


def _energy(P, fps=6):
    n = int(P.duration * fps); prev = None; out = []
    for i in range(n):
        t = i / fps; g = np.asarray(P.frame_at(t, int(t * P.fps), []).convert("L"), dtype=np.float32)
        out.append(0.0 if prev is None else float(np.abs(g - prev).mean())); prev = g
    return np.array(out), fps


def analyze(spec_path, fmt=None):
    spec_path = spec_path if isinstance(spec_path, str) else str(spec_path); import os
    base = os.path.dirname(os.path.abspath(spec_path)); spec = load_spec(spec_path); small = _small(spec, base, fmt)
    P = Project(copy.deepcopy(spec), base, fmt=fmt)                                       # as it will ship (for cues, durations)
    full = Project(copy.deepcopy(spec), base, fmt=small)
    flat = copy.deepcopy(spec); flat.update({"motion": "none", "backdrop": "none", "look": "clean", "punch": False})
    for sc in flat["scenes"]: sc.pop("camera", None)
    content = Project(flat, base, fmt=small)
    e_full, fps = _energy(full); e_cont, _ = _energy(content)
    thr = 0.18
    still_runs, run, start = [], 0, 0
    for i, v in enumerate(e_cont):
        if v < thr:
            if run == 0: start = i
            run += 1
        else:
            if run / fps > 0.6: still_runs.append((start / fps, run / fps))
            run = 0
    if run / fps > 0.6: still_runs.append((start / fps, run / fps))
    longest = max([d for _, d in still_runs], default=0.0)
    first_motion = next((i / fps for i, v in enumerate(e_cont) if v >= thr), P.duration)
    cues = P.cues(); types = {sc["type"] for _, _, sc in P.timeline}; dur = P.duration
    warns = sorted(set(P.warnings) | set(w for w in _canvas_warnings(P)))
    m = {
        "duration": round(dur, 1), "scenes": len(P.timeline), "scene_mean": round(dur / len(P.timeline), 2), "cuts_per_min": round((len(P.timeline) - 1) / dur * 60, 1),
        "cue_density": round(len(cues) / dur, 2), "still_stretch": round(longest, 2), "still_runs": [(round(a, 1), round(d, 1)) for a, d in still_runs],
        "hook_motion": round(first_motion, 2), "hook_scene": round(P.timeline[0][2]["dur"], 2),
        "content_motion": round(float(e_cont.mean()), 2), "ambient_motion": round(float(max(0.0, e_full.mean() - e_cont.mean())), 2),
        "variety": round(len(types) / dur * 10, 2), "scene_types": sorted(types),
        "music": bool(P.music), "narration": bool(P.voiceover), "word_synced": any("_words" in sc for _, _, sc in P.timeline), "warnings": warns,
    }
    return m, advise(m, spec)


def _canvas_warnings(P):
    out = []
    for a, b, sc in P.timeline:
        w = []; P._scene_canvas(P.timeline.index((a, b, sc)), min(sc["dur"] * 0.8, sc["dur"] - 0.05), w); out += w
    return out


def advise(m, spec):
    """[(status, label, value, target, advice)] where status is ok | warn | fail."""
    rows = []
    def row(ok, label, value, target, advice, fail=False): rows.append(("ok" if ok else ("fail" if fail else "warn"), label, value, target, "" if ok else advice))
    row(m["cue_density"] >= 3.0, "sound cues per second", m["cue_density"], "3 or more", "Add sound to events: set sfx_density \"rich\", add a manual cue sheet, or use scenes that cue every reveal (bullets, stat, grid, flow).")
    row(m["still_stretch"] <= 1.2, "longest content-still stretch (s)", m["still_stretch"], "1.2 or less",
        "Nothing meaningful moves at %s. Shorten that scene, add an element that builds, or use a scene with progress (stat, grid, flow, chart)." % (", ".join(f"{a}s (for {d}s)" for a, d in sorted(m["still_runs"], key=lambda r: -r[1])[:3]) or "somewhere"), fail=m["still_stretch"] > 2.5)
    row(m["hook_motion"] <= 0.6, "first content motion (s)", m["hook_motion"], "0.6 or less", "The opening starts slowly. Lead with a title or slam that begins immediately.")
    kind = spec.get("kind", "general")
    if kind in ("ad", "reel"): row(m["hook_scene"] <= 3.6, "opening scene length (s)", m["hook_scene"], "3.6 or less", "Shorten the hook; viewers decide in the first seconds.")
    row(2.2 <= m["scene_mean"] <= 6.5, "average scene length (s)", m["scene_mean"], "2.2 to 6.5", "Scenes are %s. Vary the pace: mix short punches with a longer proof scene." % ("too long" if m["scene_mean"] > 6.5 else "too short"))
    row(m["variety"] >= 1.5, "scene types per 10 s", m["variety"], "1.5 or more", "Repetitive. Use different visual verbs: strike for contrast, grid for scale, flow for a process, odometer for a number.")
    row(m["music"] or m["narration"], "has music or narration", "yes" if (m["music"] or m["narration"]) else "no", "yes", "Silent video. Leave music on auto or add narration.")
    row(not m["narration"] or m["word_synced"], "narration synced to words", "yes" if m["word_synced"] else "no", "yes when narrated", "Set \"align\": true and run `motionspec voice` so visuals land on the words.")
    row(m["content_motion"] >= 0.6, "content motion (mean)", m["content_motion"], "0.6 or more", "Scenes change little by themselves. The drift and backdrop are not a substitute: add builds, counters or draws.")
    row(not m["warnings"], "text fits the safe area", "yes" if not m["warnings"] else f"{len(m['warnings'])} issue(s)", "yes", "; ".join(m["warnings"][:3]))
    return rows


def format_report(m, rows):
    lines = [f"{m['duration']} s, {m['scenes']} scenes, {m['cuts_per_min']} cuts/min. Content motion {m['content_motion']}, ambient {m['ambient_motion']} (ambient does not count).", ""]
    for st, label, val, tgt, adv in rows:
        lines.append(f"  {'ok  ' if st == 'ok' else 'WARN' if st == 'warn' else 'FAIL'}  {label}: {val}   (target {tgt})")
        if adv: lines.append(f"        fix: {adv}")
    bad = [r for r in rows if r[0] != "ok"]
    lines += ["", "All checks pass." if not bad else f"{len(bad)} thing(s) to improve before this ships."]
    return "\n".join(lines)
