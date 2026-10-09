# Voice and narration

Write the script first. One short sentence (or two) per scene, in the scene's `say`. Say numbers the way they sound ("twenty eight seconds"), spell acronyms as a speaker would ("J S O N", "M P 4").

## ElevenLabs
1. Pick a voice in the ElevenLabs voice library; copy its voice id.
2. In the spec: `"voice": {"provider": "elevenlabs", "voice_id": "<id>", "model": "eleven_multilingual_v2"}`.
3. Set `ELEVENLABS_API_KEY` in your own environment (PowerShell: `$env:ELEVENLABS_API_KEY = "..."`, bash: `export ELEVENLABS_API_KEY=...`). Never paste it into a chat or a file in the repo.
4. `motionspec voice spec.json --write` generates one clip per scene, joins them with a short gap, writes `assets/voice_<hash>.mp3` plus a timing file, and sets `voiceover`, `align` and `captions_style` in the spec. Unchanged text is cached, so re-running costs nothing.
Cost: roughly 4 US cents for a 35 second narration (about 400 characters on a standard plan; check your plan).

## Local voice
`motionspec voice spec.json --provider local --write`. Uses Windows SAPI, macOS `say` or Linux `espeak-ng`. Free and offline, plainer than ElevenLabs. Some sandboxed environments block it.

## Your own recording
Record the `say` lines in order (phone or microphone), then `motionspec voice spec.json --provider file --file rec.mp3 --write`. Leave a clear pause between sentences: the aligner matches sentences to speech segments. Install `faster-whisper` for word-accurate timing.

## What changes in the video
- Each scene lasts at least as long as its narration (plus a short lead and tail), so cuts land on the speech.
- Title words, list items, flow nodes and counters appear on the word that names them (`motionspec/sync.py`).
- Captions follow the words; `"captions_style": "karaoke"` highlights each word as it is spoken.
- Music and sound effects dip under the voice automatically.
