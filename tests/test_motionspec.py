"""Run with: python -m unittest discover -s tests   (no third-party test runner needed)."""
import json
import math
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from motionspec import captions, ease, paths, policy                                  # noqa: E402
from motionspec.layout import get_format                                              # noqa: E402
from motionspec.render import Project, SpecError, load_spec, stills                   # noqa: E402
from motionspec.theme import ThemeError, contrast, load_theme, rgb                    # noqa: E402
from motionspec.validate import json_schema, validate                                 # noqa: E402

EX = os.path.join(ROOT, "examples")


def spec(**kw):
    s = {"scenes": [{"type": "title", "dur": 3, "lines": ["Hi"]}]}; s.update(kw); return s


class Ease(unittest.TestCase):
    def test_endpoints_and_finite(self):
        for name, f in ease.EASINGS.items():
            self.assertAlmostEqual(f(0.0), 0.0, 6, name); self.assertAlmostEqual(f(1.0), 1.0, 6, name)
            for i in range(101): self.assertTrue(math.isfinite(f(i / 100)), name)

    def test_unknown_ease(self):
        with self.assertRaises(ValueError): ease.get_ease("nope")

    def test_bezier_matches_linear(self):
        f = ease.bezier(0.25, 0.25, 0.75, 0.75)
        for x in (0.1, 0.5, 0.9): self.assertAlmostEqual(f(x), x, 2)


class Theme(unittest.TestCase):
    def test_bad_colour_names_the_value(self):
        with self.assertRaises(ThemeError) as cm: rgb("red")
        self.assertIn("red", str(cm.exception))

    def test_unknown_theme_key(self):
        with self.assertRaises(ThemeError): load_theme({"extends": "midnight", "colour": "#fff"})

    def test_builtin_themes_are_accessible(self):
        for n in ("midnight", "paper", "signal"): self.assertEqual(load_theme(n).check(), [], n)

    def test_contrast(self): self.assertGreater(contrast("#FFFFFF", "#000000"), 20)


class Layout(unittest.TestCase):
    def test_presets_and_custom(self):
        self.assertEqual((get_format("square").W, get_format("square").H), (1080, 1080))
        self.assertEqual(get_format("1280x720").W, 1280)

    def test_bad_format(self):
        for bad in ("huge", "1081x1080", "10x10"):
            with self.assertRaises(ValueError): get_format(bad)


class Validate(unittest.TestCase):
    def test_examples_valid(self):
        for f in os.listdir(EX):
            if f.endswith(".json"): self.assertEqual(validate(load_spec(os.path.join(EX, f))), [], f)

    def test_unknown_scene_suggests(self):
        errs = validate(spec(scenes=[{"type": "titel", "dur": 2, "lines": ["x"]}]))
        self.assertTrue(any("title" in e for e in errs), errs)

    def test_unknown_field_suggests(self):
        errs = validate(spec(scenes=[{"type": "stat", "dur": 3, "value": 1, "captoin": "x"}]))
        self.assertTrue(any("caption" in e for e in errs), errs)

    def test_bool_is_not_a_number(self):
        self.assertTrue(validate(spec(scenes=[{"type": "title", "dur": True, "lines": ["x"]}])))

    def test_empty_lists_and_bounds(self):
        self.assertTrue(validate(spec(scenes=[{"type": "bullets", "dur": 3, "items": []}])))
        self.assertTrue(validate(spec(scenes=[{"type": "grid", "dur": 3, "total": 5, "hit": 9}])))
        self.assertTrue(validate(spec(scenes=[{"type": "title", "dur": 0.1, "lines": ["x"]}])))
        self.assertTrue(validate(spec(scenes=[])))

    def test_negative_bars_rejected(self):
        self.assertTrue(validate(spec(scenes=[{"type": "bars", "dur": 3, "items": [{"label": "a", "value": -1}]}])))

    def test_schema_lists_every_scene(self):
        names = {v["title"] for v in json_schema()["properties"]["scenes"]["items"]["oneOf"]}
        self.assertTrue({"title", "grid", "chart", "endcard", "slam"} <= names)


class Sandbox(unittest.TestCase):
    def test_rejects_urls_and_escapes(self):
        paths.configure(ROOT)
        for bad in ("http://x/y.png", "concat:a|b", "../outside.png", os.path.abspath(os.sep)):
            with self.assertRaises(paths.PathError, msg=bad): paths.resolve(bad, must_exist=False)

    def test_missing_file_suggests(self):
        paths.configure(EX)
        with self.assertRaises(paths.PathError) as cm: paths.resolve("assets/dashbord.png")
        self.assertIn("dashboard.png", str(cm.exception))


class Policy(unittest.TestCase):
    def test_banned_required_numbers(self):
        s = spec(scenes=[{"type": "title", "dur": 3, "lines": ["Guaranteed 97 wins"]}], facts=["f1"])
        with tempfile.TemporaryDirectory() as d:
            json.dump({"facts": [{"id": "f1", "numbers": ["12"]}]}, open(os.path.join(d, "f.json"), "w"))
            errs, _ = policy.lint(s, {"banned": ["guaranteed"], "required_any": ["not proof"], "facts_file": "f.json"}, d)
        text = "\n".join(errs); self.assertIn("banned", text); self.assertIn("97", text); self.assertIn("must include", text)


class CliLint(unittest.TestCase):
    def run_cli(self, *a):
        return subprocess.run([sys.executable, "-m", "motionspec", *a], cwd=ROOT, capture_output=True, text=True)

    def test_policy_facts_resolve_next_to_the_policy_not_the_spec(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "specs"))
            with open(os.path.join(d, "facts.json"), "w") as f: json.dump({"facts": [{"id": "a", "numbers": ["14"]}]}, f)
            with open(os.path.join(d, "policy.json"), "w") as f: json.dump({"facts_file": "facts.json"}, f)
            with open(os.path.join(d, "specs", "s.json"), "w") as f:
                json.dump({"policy": "../policy.json", "facts": ["a"], "scenes": [{"type": "title", "dur": 3, "lines": ["14 of them"]}]}, f)
            r = self.run_cli("lint", os.path.join(d, "specs", "s.json")); self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_missing_files_give_a_clean_error_not_a_traceback(self):
        r = self.run_cli("lint", "does-not-exist.json"); self.assertNotEqual(r.returncode, 0); self.assertNotIn("Traceback", r.stderr)

    def test_restricted_fact_needs_approval(self):
        s = spec(facts=["a"]); fp = {"facts": [{"id": "a", "numbers": [], "restricted": True}]}
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "f.json"), "w") as fh: json.dump(fp, fh)
            self.assertTrue(any("restricted" in e for e in policy.lint(s, {"facts_file": "f.json"}, d)[0]))
            s["approved_facts"] = ["a"]; self.assertEqual(policy.lint(s, {"facts_file": "f.json"}, d)[0], [])


class Align(unittest.TestCase):
    def test_sentences_snap_to_speech_segments(self):
        import wave
        import numpy as np
        from motionspec import align
        sr = 48000; tt = lambda d: np.arange(int(d * sr)) / sr
        burst = lambda d, f: 0.4 * np.sin(2 * np.pi * f * tt(d)) * (0.6 + 0.4 * np.sin(2 * np.pi * 4 * tt(d)))
        sil = lambda d: np.zeros(int(d * sr))
        a = np.concatenate([sil(0.3), burst(1.5, 180), sil(0.6), burst(1.2, 200), sil(0.6), burst(1.8, 170), sil(0.3)])
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "v.wav")
            with wave.open(p, "wb") as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes((a * 32767).astype(np.int16).tobytes())
            words = "Describe the video in text. Check before you render. Then get an MP4 out.".split()
            out = align.heuristic(p, words)
        self.assertEqual(len(out), len(words))
        for idx, (t0, t1) in ((0, (0.30, 1.80)), (5, (2.40, 3.60)), (9, (4.20, 6.00))):          # first word of each sentence
            self.assertAlmostEqual(out[idx]["t0"], t0, delta=0.08, msg=out[idx])
        self.assertAlmostEqual(out[-1]["t1"], 6.0, delta=0.08)


class VoiceLed(unittest.TestCase):
    """Narration route, with a stand-in for the ElevenLabs call (tone length follows the word count) so no key or network is needed."""

    def fake_tts(self, text, cfg):
        n = len(text.split()); out = tempfile.mktemp(suffix=".mp3")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=220:duration=%.2f" % (0.3 * n), "-q:a", "5", out], check=True)
        return open(out, "rb").read()

    def test_per_scene_narration_gives_exact_timing_and_synced_render(self):
        from motionspec import voice
        spec = {"format": "square", "align": True, "captions_style": "karaoke", "voice": {"provider": "elevenlabs", "voice_id": "x"},
                "scenes": [{"type": "title", "dur": 2, "lines": ["Hello there"], "say": "Hello there"},
                           {"type": "bullets", "dur": 2, "items": ["First thing", "Second thing"], "say": "Here is the first thing, then the second thing."},
                           {"type": "endcard", "dur": 2}]}
        old = voice._elevenlabs; voice._elevenlabs = self.fake_tts
        try:
            with tempfile.TemporaryDirectory() as d:
                os.environ["ELEVENLABS_API_KEY"] = "test"
                audio, data = voice.synthesize(spec, d)
                self.assertEqual([e["scene"] for e in data["scenes"]], [0, 1])
                self.assertLess(data["scenes"][0]["t1"], data["scenes"][1]["t0"])                 # a gap separates scenes
                spec["voiceover"] = audio; sp = os.path.join(d, "s.json")
                with open(sp, "w") as fh: json.dump(spec, fh)
                P = Project(load_spec(sp), d)
                self.assertIsNotNone(P.voice_segments); self.assertEqual(len(P.voice_segments), 2)
                self.assertTrue(all("_words" in sc for _, _, sc in P.timeline[:2]))
                self.assertGreaterEqual(P.timeline[1][2]["dur"], data["scenes"][1]["t1"] - data["scenes"][1]["t0"])   # never cut the speech short
                from motionspec import sync
                sc = P.timeline[1][2]; self.assertGreater(sync.find(sc, "second"), sync.find(sc, "first"))             # words found in spoken order
                r = subprocess.run([sys.executable, "-m", "motionspec", "render", sp, "-o", os.path.join(d, "o.mp4"), "--jobs", "2"], cwd=ROOT, capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, r.stderr)
        finally:
            voice._elevenlabs = old; os.environ.pop("ELEVENLABS_API_KEY", None)

    def test_missing_key_and_bad_provider_explain_themselves(self):
        from motionspec import voice
        os.environ.pop("ELEVENLABS_API_KEY", None)
        with self.assertRaises(voice.VoiceError) as cm: voice._elevenlabs("hi", {"voice_id": "x"})
        self.assertIn("ELEVENLABS_API_KEY", str(cm.exception))
        with self.assertRaises(voice.VoiceError): voice.synthesize({"scenes": [{"type": "title", "dur": 2, "lines": ["x"], "say": "x"}]}, tempfile.gettempdir(), provider="nope")
        with self.assertRaises(voice.VoiceError): voice.synthesize({"scenes": [{"type": "title", "dur": 2, "lines": ["x"]}]}, tempfile.gettempdir(), provider="local")


class AlignRobust(unittest.TestCase):
    def test_extra_pauses_inside_sentences_are_merged(self):
        from motionspec import align
        segs = [(0.0, 1.0), (1.2, 2.0), (3.0, 4.0), (4.1, 5.0), (6.2, 7.0)]            # 5 segments, 3 sentences: smallest gaps merge first
        merged = align._merge_to(segs, 3)
        self.assertEqual(len(merged), 3); self.assertEqual(merged[0], (0.0, 2.0)); self.assertEqual(merged[1], (3.0, 5.0)); self.assertEqual(merged[2], (6.2, 7.0))


class Analyze(unittest.TestCase):
    def test_analyzer_reports_every_check_and_flags_a_dead_scene(self):
        from motionspec.analyze import analyze
        sp = {"kind": "ad", "format": "square", "scenes": [{"type": "title", "dur": 3, "lines": ["Hi"]}, {"type": "note", "dur": 9, "text": "Static for a long while."}]}
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "s.json")
            with open(p, "w") as fh: json.dump(sp, fh)
            m, rows = analyze(p)
        self.assertGreaterEqual(len(rows), 9); self.assertTrue(any(r[0] != "ok" for r in rows))
        self.assertIn("still_stretch", m); self.assertGreater(m["still_stretch"], 1.2)


class Shapes(unittest.TestCase):
    def test_sub_pixel_and_inverted_shapes_do_not_crash(self):
        from motionspec.canvas import Canvas
        from motionspec.layout import get_format
        from motionspec.theme import load_theme
        c = Canvas(get_format("square"), load_theme("midnight"))
        for box in ((100, 100, 100.2, 140), (100, 100, 140, 100.3), (150, 150, 100, 100), (10, 10, 10, 10)):
            c.rect(box, "accent", 1.0, radius=28); c.shadow_rect(box, 28, 24, 0.5)
        c.dot(50, 50, 0.2); c.line([(5, 5), (5, 5)], 3)

    def test_every_scene_survives_every_moment_of_its_build(self):
        # the spring-in of nodes, bars and cards passes through tiny sizes: draw each gallery scene at many early times in two formats
        P = Project(load_spec(os.path.join(EX, "scene_gallery.json")), EX, fmt="reel")
        for k, (a, b, sc) in enumerate(P.timeline):
            for dt in (0.0, 0.01, 0.03, 0.07, 0.15, 0.31, 0.62, 1.1):
                P._scene_canvas(k, min(dt, sc["dur"] - 0.01), [])


class Transitions(unittest.TestCase):
    def test_push_transition_is_smooth_not_ghosted(self):
        import numpy as np
        sp = {"format": "square", "transition": "push", "scenes": [{"type": "title", "dur": 3, "lines": ["A"]}, {"type": "title", "dur": 3, "lines": ["B"]}]}
        P = Project(sp, EX); a, b, _ = P.timeline[0]; mid = b - 0.25
        f = np.asarray(P.frame_at(mid, int(mid * P.fps)).convert("L"), dtype=np.float32)
        before = np.asarray(P.frame_at(b - 1.0, 0).convert("L"), dtype=np.float32)
        self.assertGreater(float(np.abs(f - before).mean()), 1.0)                     # the push really moved the picture
        rows = f.mean(axis=1); self.assertLess(float(np.abs(np.diff(rows)).max()), 60)  # and no hard edge from stacked copies


class Cues(unittest.TestCase):
    def test_every_scene_builds_valid_cues(self):
        from motionspec import audio
        P = Project(load_spec(os.path.join(EX, "scene_gallery.json")), EX)
        cues = P.cues(); self.assertGreater(len(cues), 40)
        for cue in cues: self.assertIn(cue[1], audio.SOUNDS); self.assertGreaterEqual(cue[0], 0)
        self.assertEqual(cues, sorted(cues, key=lambda c: c[0]))

    def test_cues_are_dense_by_default_and_can_be_thinned(self):
        sp = load_spec(os.path.join(EX, "ad_skill.json")); rich = len(Project(sp, EX).cues())
        sp["sfx_density"] = "light"; light = len(Project(sp, EX).cues()); sp["sfx_density"] = "off"
        self.assertGreater(rich, light); self.assertEqual(Project(sp, EX).cues(), [])


class Emphasis(unittest.TestCase):
    def test_emphasis_spans_words(self):
        from motionspec.scenes.text import _tokens
        self.assertEqual(_tokens("for *a video*."), [("for", False), ("a", True), ("video.", True)])
        self.assertEqual(_tokens("Make it *pop* now"), [("Make", False), ("it", False), ("pop", True), ("now", False)])


class Warnings(unittest.TestCase):
    def test_code_typing_that_cannot_finish_is_flagged(self):
        sp = {"scenes": [{"type": "code", "dur": 2, "cps": 10, "lines": ["x" * 80]}]}
        self.assertTrue(any("typing needs" in w for w in Project(sp, EX).warnings))
        sp["scenes"][0]["cps"] = 200
        self.assertFalse(any("typing needs" in w for w in Project(sp, EX).warnings))


class Music(unittest.TestCase):
    def test_generated_music_is_deterministic_and_sane(self):
        import numpy as np
        from motionspec import music
        for mood in music.MOODS:
            a = music.generate(6, mood, "t"); self.assertEqual(len(a), 6 * 48000); self.assertTrue(np.isfinite(a).all())
            self.assertLess(float(np.abs(a).max()), 0.8); self.assertGreater(float(np.sqrt((a ** 2).mean())), 0.05)
        self.assertTrue(np.array_equal(music.generate(4, "calm", "x"), music.generate(4, "calm", "x")))
        self.assertFalse(np.array_equal(music.generate(4, "calm", "x"), music.generate(4, "calm", "y")))

    def test_music_option_resolution_and_validation(self):
        from motionspec.render import Project
        self.assertEqual(Project._music({"kind": "ad", "id": "a"})["mood"], "upbeat")
        self.assertEqual(Project._music({"kind": "explainer"})["mood"], "calm")
        self.assertIsNone(Project._music({"music": "off"}))
        self.assertTrue(validate(spec(music={"mood": "nope"})))
        self.assertEqual(validate(spec(music={"mood": "warm", "db": -6})), [])

    def test_every_render_has_an_audio_track_by_default(self):
        with tempfile.TemporaryDirectory() as d:
            s = os.path.join(d, "s.json"); json.dump({"format": "square", "scenes": [{"type": "title", "dur": 1.2, "lines": ["Hi"]}]}, open(s, "w"))
            r = subprocess.run([sys.executable, "-m", "motionspec", "render", s, "-o", os.path.join(d, "o.mp4"), "--jobs", "2"], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            info = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0", os.path.join(d, "o.mp4")], capture_output=True, text=True).stdout
            self.assertIn("audio", info)


class Quickstart(unittest.TestCase):
    def test_quickstart_example_renders(self):
        with tempfile.TemporaryDirectory() as d:
            files, _ = stills(os.path.join(EX, "quickstart", "spec.json"), [1.0, 6.0, 11.0], d)
            self.assertEqual(len(files), 3)


class Captions(unittest.TestCase):
    def test_build_and_srt(self):
        caps = captions.build([{"dur": 4, "say": "one two three four five six seven eight nine"}], max_words=5)
        self.assertEqual(len(caps), 2); self.assertLess(caps[0]["t1"], caps[1]["t1"])
        self.assertIn("-->", captions.to_srt(caps))


class Render(unittest.TestCase):
    def test_every_scene_every_format_renders(self):
        for name in ("data_story", "product_ad", "explainer"):
            for fmt in ("reel", "landscape", "square"):
                with tempfile.TemporaryDirectory() as d:
                    files, _ = stills(os.path.join(EX, name + ".json"), [0.2, 2.5], d, fmt)
                    self.assertEqual(len(files), 2); [self.assertTrue(os.path.getsize(f) > 2000) for f in files]

    def test_deterministic(self):
        P = Project(load_spec(os.path.join(EX, "explainer.json")), EX)
        self.assertEqual(P.frame(40).tobytes(), P.frame(40).tobytes())

    def test_bad_spec_reports_every_problem(self):
        with self.assertRaises(SpecError) as cm: Project({"scenes": [{"type": "nope", "dur": 1}, {"type": "bars", "dur": 3}]}, EX)
        self.assertGreaterEqual(str(cm.exception).count("\n  - "), 2)

    def test_end_to_end_mp4(self):
        with tempfile.TemporaryDirectory() as d:
            s = os.path.join(d, "s.json"); json.dump({"format": "square", "scenes": [{"type": "title", "dur": 1.2, "lines": ["Hello"]}]}, open(s, "w"))
            r = subprocess.run([sys.executable, "-m", "motionspec", "render", s, "-o", os.path.join(d, "o.mp4"), "--jobs", "2"], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr); self.assertTrue(os.path.getsize(os.path.join(d, "o.mp4")) > 1000)


if __name__ == "__main__":
    unittest.main()
