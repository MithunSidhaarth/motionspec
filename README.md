# motionspec

Describe a video in JSON. Get an MP4. Every frame is a pure function of time, so a video is a text file you can diff, validate, review and re-render for any screen shape.

```
spec.json  ->  validate  ->  preview (contact sheet)  ->  render (parallel)  ->  mp4 (+ srt)
```

Made for solo founders and small teams who need credible, repeatable videos for several products: explainers, feed ads, reels and stories, product demos, data stories. One brand file per product; one spec re-flows to every format.

## Quick start

```bash
pip install -e .            # needs Python 3.10+, ffmpeg on PATH
motionspec doctor           # plain-English check of your setup
motionspec new my-video --kind explainer     # explainer | ad | reel | demo
motionspec preview my-video/spec.json -o my-video/preview.png
motionspec render  my-video/spec.json -o my-video/out.mp4
motionspec render  my-video/spec.json --format all -o my-video/out.mp4   # reel, 4:5, square, landscape
```

A 40 s 1080p video with sound renders in about half a minute on a laptop, because frames are independent and are drawn in parallel.

## What a spec looks like

```json
{
  "spec_version": 1, "kind": "ad", "format": "portrait", "theme": "theme.json",
  "scenes": [
    {"type": "strike", "dur": 3.5, "wrong": "Reports take all week", "right": "Reports take ten minutes"},
    {"type": "image",  "dur": 5,   "src": "assets/dashboard.png", "caption": "Everything in one place", "camera": {"zoom": [1, 1.05]}},
    {"type": "endcard","dur": 4,   "button": "Start free"}
  ]
}
```

- **Scenes:** `title`, `section`, `bullets`, `steps`, `quote`, `note`, `slam`, `strike`, `stat`, `bars`, `chart`, `grid`, `compare`, `timeline`, `image`, `clip`, `code`, `endcard`. Run `motionspec scenes` for every field.
- **Themes:** colours, fonts, logo, brand name and tagline are data (`theme.json`, or a built-in: `midnight`, `paper`, `signal`). The engine hardcodes no brand.
- **Formats:** `reel`, `story`, `portrait` (4:5), `square`, `landscape`, `landscape4k`, or any even `WxH`.
- **Sound:** generated cues, optional voiceover and music bed (ducked under speech), loudness-normalised. `autotime` snaps scene lengths to the pauses in a voiceover; `say` text becomes captions and an `.srt`.
- **Finish:** per-scene camera (zoom, pan, drift), optional motion blur, bloom and grain.

## Why you can trust it

- **Validation with paths:** `scenes[2] (bars).items[0].value: negative values are not supported`, with "did you mean" suggestions. `motionspec schema` exports a JSON Schema for editors and LLMs.
- **Policy as data:** `motionspec lint` enforces your own rules (banned words, required disclaimers, numbers that must come from a facts file) from a `policy.json`.
- **Sandboxed files:** a spec can only read inside its project folder; URLs and ffmpeg protocols are rejected.
- **Deterministic:** the same spec and frame always give the same pixels (tested). Text that would leave the safe area is reported.
- **Tested:** `python -m unittest discover -s tests` (24 tests: easing, validation, sandbox, policy, rendering in every format, end to end MP4).

## Extend it

```python
# my_scenes/badge.py  ->  motionspec render spec.json --plugins my_scenes
from motionspec.scenes import scene

@scene("badge", fields={"text": (str, True)}, cues=lambda s: [(0.1, "pop")], desc="A pill with text.")
def badge(c, t, s):
    c.rect((c.W*0.3, c.H*0.45, c.W*0.7, c.H*0.55), "accent", radius=c.S(60))
    c.text(c.cx, c.H*0.47, s["text"], "bold", 56, "accent_text")
```

Plugins run arbitrary Python: load only code you trust, and only via `--plugins`, never from a spec.

## Claude skill

`skill/motionspec` teaches Claude the workflow (brief, facts, spec, validate, preview, render, post pack, your approval). Copy it to `~/.claude/skills/`.

## When not to use it

For hand-animated, one-off cinematic work, use After Effects or a real editor. motionspec is for videos that are mostly text, numbers, screenshots and clips that you want to make quickly and repeatably.

## Status

Version 0.1. Fonts: the engine looks for system fonts and warns when it cannot find any; bundle an open-licence font in `motionspec/fonts/` for identical output on every machine. Licence: all rights reserved for now (see `LICENSE`).

## Acknowledgements

The "video as code, locked to a voiceover" idea was inspired by the public *Motion as Code* starter guide. No code or assets from it are included; this is an independent implementation.
