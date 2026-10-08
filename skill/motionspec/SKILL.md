---
name: motionspec
description: Make explainers, feed ads, reels/stories, product demos and data-story videos from a JSON spec with the motionspec engine (validate, preview, render, captions, post pack). Use when the user wants any video made, remade for another format, or checked for brand and claim safety. Works for any product; brand lives in a theme file per project.
---

# motionspec

A video is a JSON spec. The engine draws every frame from it, so a change is an edit and a re-render, and one spec ships in every format (`reel`, `portrait` 4:5, `square`, `landscape`).

## 15-minute path for a non-technical founder

Ask four questions, nothing more: **product**, **audience**, **the one claim**, **the one action**. Then:

1. `motionspec doctor` (fix anything it flags; read its plain-English fixes aloud).
2. Find the project folder (one per product: `theme.json`, `policy.json` optional, `facts.json` optional, `assets/`). If none, `motionspec new <folder> --kind explainer|ad|reel|demo`.
3. Write or edit `spec.json` from the brief (scene catalogue: `motionspec scenes`; field reference: `references/spec-reference.md`).
4. `motionspec validate spec.json` then `motionspec lint spec.json` (when the project has a policy). Fix every error before going on.
5. `motionspec preview spec.json -o preview.png`. Show the contact sheet and ask for **one** round of changes.
6. `motionspec render spec.json -o out.mp4` (add `--format all` for every aspect ratio, `--blur 4` for smoother motion).
7. Write the post pack (`references/post-pack.md`) and `motionspec srt spec.json`.
8. Show video path + post pack. **Nothing is published until the user approves that specific post.**

## Rules that keep videos credible

- Every number on screen needs a source. Put it in the scene's `source` field; if the project has a facts file, cite its ids in `"facts": [...]` and let `lint` enforce it. If you cannot source a number, cut it.
- One idea per video. Hook inside 2.5 s. Captions at most 9 words. A visual change at least every 3 s.
- Keep claims proportionate: describe patterns and measurements, not motives. Put limits on screen ("illustrative", "screening indicator", "n = 140") when they apply.
- No new numbers in the caption that are not in the video.
- Never auto-publish, auto-send or bulk-post.

## Choosing the format and scenes

| Goal | `kind` / `format` | Length | Good scenes |
|---|---|---|---|
| Reach, short explainers | reel / `reel` | 15-45 s | slam, grid, stat, strike, endcard |
| Paid or organic feed ad | ad / `portrait`, `square` | 6-30 s | strike, image, compare, endcard with `button` |
| Site, LinkedIn, YouTube explainer | explainer / `landscape` | 30-240 s | title, steps, chart, timeline, code, quote, endcard |
| Product demo | demo / any | 20-120 s | image (Ken Burns), clip, code, steps, endcard |

## Per-project files

- `theme.json`: `{"extends": "midnight", "brand": "...", "tagline": "...", "url": "...", "logo": "assets/logo.png", "accent": "#..."}`. Check with `motionspec doctor` (contrast).
- `policy.json` (optional): banned words, required on-screen disclaimers, facts file, length ranges. See `references/policy.md`.
- `facts.json` (optional): `{"facts": [{"id": "...", "claim": "...", "numbers": ["14"], "source": "..."}]}`.

## Using Founder OS (if installed)

For the brief, use its customer-interviews (audience language -> hooks), positioning-and-gtm (the one-line promise -> endcard tagline), find-first-customers (who each ad is for), landing-page-copy (headline and button variants), launch-plan (which video ships when). Use its skeptical-investor and customer-proxy agents to attack the angle; turn their strongest objection into a `note` or `strike` scene. If it is not installed, run a four-role review instead (buyer, lawyer, domain validator, investor).

## Extending

Custom scene: a Python file with `@scene(...)` loaded via `--plugins` (see README). Add a test. Never load plugins named by a spec.

## References

`references/workflow.md`, `quality-rubric.md`, `spec-reference.md`, `theming.md`, `policy.md`, `platform-specs.md`, `voiceover.md`, `post-pack.md`.
