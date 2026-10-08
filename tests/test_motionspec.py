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
