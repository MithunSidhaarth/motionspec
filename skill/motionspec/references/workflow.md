# Workflow

**Brief (write first):** audience (one role) | the one thing they should repeat | the action | format and length | evidence (sources).

**Weekly rhythm:** Mon angle and sources. Tue spec, validate, lint, preview. Wed render, post pack, approval. Thu publish (the human). Fri read results; note which hook held attention in `learnings.md`.

**Variants:** one spec, `--format all`. Change one variable at a time (hook line or button text). Keep disclaimers in every variant.

**Fast loop while editing:** `motionspec still spec.json --times 1.5,6 -o stills` (single frames), `motionspec preview` (one per scene).

**Timing to speech:** write one `say` line per scene, record the voiceover, set `"voiceover": "assets/vo.mp3"` and `"autotime": true`; scene lengths snap to pauses. `motionspec srt` exports captions.

**When a published video is wrong:** correct in the first comment within the hour, fix the spec, re-render, keep the old version in git.
