# Voiceover

1. One `say` line per scene, under 14 words each.
2. Record or generate the audio; save it inside the project (`assets/vo.mp3`). Set `"voiceover": "assets/vo.mp3"` and `"autotime": true`.
3. `motionspec autotime assets/vo.mp3 --scenes 5` prints the suggested durations if you prefer to set them by hand.
4. Sound cues duck 10 dB under speech automatically. A music bed (`"music": {"src": "assets/bed.mp3", "db": -22}`) ducks too. Only use music you are licensed to use.
5. Captions come from `say`; export with `motionspec srt spec.json`.
