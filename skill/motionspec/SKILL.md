---
name: motionspec
description: Make explainers, feed ads, reels/stories, product demos and data-story videos from a JSON spec with the motionspec engine (script, narration, validate, preview, critique, render, captions, post pack). Use when the user wants any video made, remade for another format, narrated, or checked for brand and claim safety. Works for any product; brand lives in a theme file per project.
---

# motionspec

A video is a JSON spec. The engine draws every frame from it, so a change is an edit and a re-render, and one spec ships in every format (`reel`, `portrait` 4:5, `square`, `landscape`).

## The director's loop (do not skip steps)

1. **Brief** (four questions, nothing more): product, audience, the one claim, the one action. Use Founder OS skills if installed (see `references/workflow.md`).
2. **Script first.** Write the narration, one short line per scene, as each scene's `say`. Voice-led videos feel designed because every visual lands on a word; silent slideshows do not.
3. **Pick a visual verb per sentence** from `references/visual-verbs.md` (contrast -> `strike`, scale -> `grid`, a process -> `flow`, a number -> `stat` with `style: odometer`, surprise -> `slam`, a conversation or command -> `code`, a product -> `device`). A list of bullets is the last resort, not the default.
4. **Spec.** One idea per video. Hook inside 2.5 s. Reference: `references/spec-reference.md`.
5. **Narration.** Choose the voice route (below), run `motionspec voice spec.json --write`. Scenes then cut on the speech and animate on the words.
6. **Validate and lint:** `motionspec validate spec.json`, `motionspec lint spec.json` (when the project has a policy). Fix every error.
7. **Critique before rendering** (this is what makes the result good):
   - `motionspec analyze spec.json` reports content motion, longest still stretch, hook speed, sound density, rhythm and variety, with a fix for each.
   - `motionspec preview spec.json -o preview.png`, then actually look at the sheet and a few stills (`motionspec still spec.json --times 1.5,6,12`). Score against `references/quality-rubric.md`.
   - Fix the lowest scores and any WARN/FAIL, then re-run. Do at most two rounds; then show the user.
8. **Render:** `motionspec render spec.json -o out.mp4` (`--format all` for every aspect ratio, `--blur 2` for smoother motion). Music is added automatically; `"music": "off"` or `--no-music` disables it. Ask the user to listen once: the music is generated bed music.
9. **Post pack** (`references/post-pack.md`) and `motionspec srt spec.json`.
10. **Approve:** show the video path, the preview and the post pack. **Nothing is published until the user approves that specific post.**

## Narration: three routes

| Route | Command | Needs |
|---|---|---|
| **ElevenLabs** (best quality) | `motionspec voice spec.json --write` | `ELEVENLABS_API_KEY` set in the user's own environment (never ask them to paste it in chat) and `voice.voice_id` in the spec. A 35 s narration costs a few US cents. |
| **Local voice** (free, offline, plainer) | `motionspec voice spec.json --provider local --write` | Windows SAPI, macOS `say`, or Linux `espeak-ng`. May be blocked in sandboxed sessions. |
| **Your own recording** | `motionspec voice spec.json --provider file --file rec.mp3 --write` | one audio file reading the `say` lines in order. Word timing is estimated from the pauses, or exact if `faster-whisper` is installed. |

If the ElevenLabs connector is available in the session, you can generate a take with it, but it keeps the audio inside ElevenLabs and gives no file. Tell the user to download the take and use the "your own recording" route, or set the API key for the first route.

## Rules that keep videos credible

- Every number on screen needs a source (`"source"` on data scenes, or a facts file with `"facts": [...]`). If you cannot source it, cut it.
- One idea per video. Captions at most 9 words. Something meaningful changes at least every 1.2 s (`analyze` checks).
- Keep claims proportionate: describe patterns and measurements, not motives. Put limits on screen when they apply.
- No new numbers in the caption that are not in the video. Never auto-publish, auto-send or bulk-post.
- Without `faster-whisper`, word timing for a single recording is an estimate: say so.

## Choosing the format

| Goal | `kind` / `format` | Length | Good scenes |
|---|---|---|---|
| Reach, short explainers | reel / `reel` | 15-45 s | slam, grid (fall), stat, strike, flow, endcard |
| Paid or organic feed ad | ad / `portrait`, `square` | 6-30 s | strike, device, flow, compare, endcard with `button` |
| Site, LinkedIn, YouTube explainer | explainer / `landscape` | 30-240 s | title, steps, chart, timeline, code, flow, quote, endcard |
| Product demo | demo / any | 20-120 s | device, clip, code, steps, endcard |

## Per-project files

- `theme.json`: `{"extends": "midnight", "brand": "...", "tagline": "...", "url": "...", "logo": "assets/logo.png", "accent": "#..."}`.
- `policy.json` (optional): banned words, required disclaimers, facts file. `facts.json` (optional): `{"facts": [{"id", "claim", "numbers", "source"}]}`.

## Extending

Custom scene: a Python file with `@scene(...)` loaded via `--plugins`. Add a test. Never load plugins named by a spec.

## References

`references/visual-verbs.md`, `workflow.md`, `quality-rubric.md`, `spec-reference.md`, `voice.md`, `theming.md`, `policy.md`, `platform-specs.md`, `post-pack.md`.
