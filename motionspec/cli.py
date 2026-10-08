"""Command line: motionspec <command>. Commands: render, still, preview, validate, lint, doctor, scenes, schema, new, srt, autotime, gallery."""
import argparse
import json
import os
import shutil
import subprocess
import sys

from . import __version__
from .constants import SPEC_VERSION

TEMPLATES = {
    "explainer": {"kind": "explainer", "format": "landscape", "scenes": [
        {"type": "title", "dur": 3, "lines": ["Your headline here.", "One clear promise."], "accent": 1, "say": "Replace this with the first line you will say."},
        {"type": "bullets", "dur": 7, "title": "Three things to know", "numbered": True, "items": [
            {"head": "First point", "sub": "One sentence of support."}, {"head": "Second point", "sub": "One sentence of support."}, {"head": "Third point", "sub": "One sentence of support."}]},
        {"type": "stat", "dur": 5, "title": "THE NUMBER", "value": 42, "suffix": "%", "caption": "What the number means, in plain words.", "source": "Name your source"},
        {"type": "endcard", "dur": 4, "button": "Try it", "ask": "Tell people what to do next."}]},
    "ad": {"kind": "ad", "format": "portrait", "scenes": [
        {"type": "title", "dur": 2.5, "lines": ["The problem,", "in five words."], "accent": 1, "size": 100},
        {"type": "compare", "dur": 5, "title": "Before and after", "left": {"title": "Before", "items": ["Slow", "Manual"]}, "right": {"title": "With us", "items": ["Fast", "Automatic"]}},
        {"type": "endcard", "dur": 4, "button": "Get started"}]},
    "reel": {"kind": "reel", "format": "reel", "scenes": [
        {"type": "slam", "dur": 3, "words": ["STOP", "SCROLLING"], "hold": 0.8},
        {"type": "grid", "dur": 6, "total": 100, "hit": 14, "title": "14 of every 100", "label_total": "cases", "label_hit": "had the pattern", "source": "Your source"},
        {"type": "endcard", "dur": 3.5, "ask": "Follow for more."}]},
    "demo": {"kind": "demo", "format": "landscape", "scenes": [
        {"type": "title", "dur": 3, "lines": ["See it in 30 seconds"]},
        {"type": "code", "dur": 6, "title": "Install", "lines": ["$ pip install yourtool", "$ yourtool init", "Done."], "highlight": [3]},
        {"type": "endcard", "dur": 4, "button": "Read the docs"}]},
}
THEME_TEMPLATE = {"extends": "midnight", "brand": "Your Brand", "tagline": "What you do, in one line.", "url": "yourdomain.com", "accent": "#FFB020"}


def _P(a):
    from .render import Project, load_spec
    sp = os.path.abspath(a.spec)
    return Project(load_spec(sp), os.path.dirname(sp), fmt=getattr(a, "format", None), plugins=tuple(a.plugins or ()), root=a.root, allow_abs=a.allow_abs_paths)


def cmd_render(a):
    from .render import render_video
    fmts = ["reel", "portrait", "square", "landscape"] if a.format == "all" else [a.format]
    for f in fmts:
        out = a.out if len(fmts) == 1 else os.path.splitext(a.out)[0] + f"_{f}.mp4"
        w = render_video(a.spec, out, fmt=f, jobs=a.jobs, crf=a.crf, blur=a.blur, sfx=not a.no_sfx, plugins=a.plugins or (), root=a.root, allow_abs=a.allow_abs_paths)
        for x in w: print("  warning:", x)
    return 0


def cmd_still(a):
    from .render import stills
    files, warns = stills(a.spec, [float(x) for x in a.times.split(",")], a.out, a.format, a.plugins or (), a.root, a.allow_abs_paths)
    print("\n".join(files)); [print("  warning:", w) for w in warns]; return 0


def cmd_preview(a):
    from .render import contact_sheet
    p, warns = contact_sheet(a.spec, a.out, a.format, a.plugins or (), a.root, a.allow_abs_paths); print(p); [print("  warning:", w) for w in warns]; return 0


def cmd_validate(a):
    from .render import SpecError, load_spec
    from .validate import validate
    try: errs = validate(load_spec(a.spec))
    except SpecError as e: print(e); return 1
    if errs: print("\n".join(f"error: {e}" for e in errs)); return 1
    print("ok"); return 0


def cmd_lint(a):
    from .policy import lint, load_policy
    from .render import load_spec
    spec = load_spec(a.spec); spec_dir = os.path.dirname(os.path.abspath(a.spec))
    pol_path = a.policy or (os.path.join(spec_dir, spec["policy"]) if spec.get("policy") else None)
    pol = load_policy(pol_path)
    errs, warns = lint(spec, pol, os.path.dirname(os.path.abspath(pol_path)) if pol_path else spec_dir)
    [print("warn ", w) for w in warns]; [print("error", e) for e in errs]
    print("ok" if not errs else f"{len(errs)} error(s)"); return 1 if errs else 0


def cmd_scenes(a):
    from .scenes import COMMON, REGISTRY, load_builtin, load_plugins
    load_builtin(); load_plugins(a.plugins or ())
    for name, info in sorted(REGISTRY.items()):
        print(f"\n{name}: {info['desc']}")
        for k, (t, req) in info["fields"].items():
            ts = "/".join(x.__name__ for x in (t if isinstance(t, tuple) else (t,)))
            print(f"    {k}{'*' if req else ''}: {ts}")
    print(f"\nCommon to all scenes: {', '.join(COMMON)}   (* = required)"); return 0


def cmd_schema(a):
    from .validate import json_schema
    s = json.dumps(json_schema(), indent=2)
    if a.out: open(a.out, "w", encoding="utf-8").write(s); print(a.out)
    else: print(s)
    return 0


def cmd_new(a):
    os.makedirs(a.name, exist_ok=True); os.makedirs(os.path.join(a.name, "assets"), exist_ok=True)
    spec = {"spec_version": SPEC_VERSION, "id": os.path.basename(os.path.abspath(a.name)), "theme": "theme.json", **TEMPLATES[a.kind]}
    for fn, data in (("spec.json", spec), ("theme.json", THEME_TEMPLATE)):
        p = os.path.join(a.name, fn)
        if os.path.exists(p) and not a.force: print(f"exists, skipped: {p} (use --force)"); continue
        json.dump(data, open(p, "w", encoding="utf-8"), indent=2); print("created", p)
    print(f"\nNext:\n  motionspec preview {a.name}/spec.json -o {a.name}/preview.png\n  motionspec render {a.name}/spec.json -o {a.name}/out.mp4"); return 0


def cmd_srt(a):
    from . import captions
    from .render import load_spec
    sp = load_spec(a.spec); caps = captions.build(sp["scenes"], sp.get("captions"))
    open(a.out, "w", encoding="utf-8").write(captions.to_srt(caps)); print(a.out, f"({len(caps)} captions)"); return 0


def cmd_autotime(a):
    from . import autotime
    d = autotime.durations(a.audio, a.scenes); print(json.dumps(d)); print(f"total {sum(d):.1f}s"); return 0


def cmd_gallery(a):
    from .render import render_video
    ex = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples")
    if not os.path.isdir(ex): print("examples/ not found (run from a source checkout)"); return 1
    for f in sorted(os.listdir(ex)):
        if f.endswith(".json"):
            render_video(os.path.join(ex, f), os.path.join(a.out, os.path.splitext(f)[0] + ".mp4"), quiet=True); print("rendered", f)
    return 0


def cmd_doctor(a):
    from . import theme as th
    ok = True
    def row(name, good, detail, fix=""):
        nonlocal ok; ok = ok and good; print(f"{'ok  ' if good else 'FAIL'} {name}: {detail}" + (f"\n       fix: {fix}" if (not good and fix) else ""))
    row("python", sys.version_info >= (3, 10), sys.version.split()[0], "install Python 3.10 or newer")
    for mod in ("PIL", "numpy"):
        try: m = __import__(mod); row(mod, True, getattr(m, "__version__", "installed"))
        except ImportError: row(mod, False, "missing", f"pip install {'pillow' if mod == 'PIL' else mod}")
    for tool in ("ffmpeg", "ffprobe"):
        p = shutil.which(tool); v = ""
        if p:
            try: v = subprocess.run([tool, "-version"], capture_output=True, text=True, timeout=10).stdout.splitlines()[0][:60]
            except Exception: pass
        row(tool, bool(p), v or "not found on PATH", "install ffmpeg from https://ffmpeg.org/download.html and reopen the terminal")
    for kind in ("bold", "reg", "mono"):
        try: row(f"font:{kind}", True, os.path.basename(th.font_path(kind)))
        except th.ThemeError as e: row(f"font:{kind}", False, "none found", str(e))
    fonts = {k: None for k in ("bold", "reg", "mono")}
    for name in th.BUILTIN:
        notes = th.Theme(**{"name": name, **th.BUILTIN[name]}).check()
        row(f"theme:{name}", not notes, "contrast ok" if not notes else "; ".join(notes))
    print("\nAll good." if ok else "\nFix the FAIL lines above, then run `motionspec doctor` again."); return 0 if ok else 1


def build_parser():
    p = argparse.ArgumentParser(prog="motionspec", description="Describe a video in JSON. Get an MP4. Every frame is a function of time.")
    p.add_argument("--version", action="version", version=f"motionspec {__version__} (spec v{SPEC_VERSION})")
    sub = p.add_subparsers(dest="cmd", required=True)
    def spec_cmd(name, fn, help_, out=None):
        s = sub.add_parser(name, help=help_); s.add_argument("spec"); s.set_defaults(fn=fn)
        s.add_argument("--format", help="override the spec's format: reel|story|portrait|square|landscape|landscape4k|WxH" + (" or all" if name == "render" else ""))
        s.add_argument("--plugins", nargs="*", help="files or folders of custom scenes"); s.add_argument("--root", help="folder the spec may read files from (default: the spec's folder)")
        s.add_argument("--allow-abs-paths", action="store_true", help="let the spec read files outside --root")
        if out: s.add_argument("-o", "--out", default=out)
        return s
    r = spec_cmd("render", cmd_render, "render the spec to an MP4", "out.mp4")
    r.add_argument("--jobs", type=int, help="worker processes (default: cores - 1)"); r.add_argument("--crf", type=int, default=18)
    r.add_argument("--blur", type=int, help="motion-blur sub-frames (1 = off, 4-8 = smooth)"); r.add_argument("--no-sfx", action="store_true")
    s = spec_cmd("still", cmd_still, "render single frames as PNG", "stills"); s.add_argument("--times", default="1.5", help="comma-separated seconds")
    spec_cmd("preview", cmd_preview, "one still per scene on a contact sheet", "preview.png")
    v = sub.add_parser("validate", help="check a spec; prints every problem with its path"); v.add_argument("spec"); v.set_defaults(fn=cmd_validate)
    l = sub.add_parser("lint", help="check content rules from a policy file"); l.add_argument("spec"); l.add_argument("--policy"); l.set_defaults(fn=cmd_lint)
    sc = sub.add_parser("scenes", help="list scene types and their fields"); sc.add_argument("--plugins", nargs="*"); sc.set_defaults(fn=cmd_scenes)
    sh = sub.add_parser("schema", help="print the JSON Schema for specs"); sh.add_argument("-o", "--out"); sh.set_defaults(fn=cmd_schema)
    n = sub.add_parser("new", help="scaffold a project folder"); n.add_argument("name"); n.add_argument("--kind", choices=sorted(TEMPLATES), default="explainer"); n.add_argument("--force", action="store_true"); n.set_defaults(fn=cmd_new)
    sr = sub.add_parser("srt", help="export captions as SRT"); sr.add_argument("spec"); sr.add_argument("-o", "--out", default="captions.srt"); sr.set_defaults(fn=cmd_srt)
    at = sub.add_parser("autotime", help="suggest scene durations from a voiceover's pauses"); at.add_argument("audio"); at.add_argument("--scenes", type=int, required=True); at.set_defaults(fn=cmd_autotime)
    g = sub.add_parser("gallery", help="render every example"); g.add_argument("-o", "--out", default="gallery"); g.set_defaults(fn=cmd_gallery)
    d = sub.add_parser("doctor", help="check your setup and explain any problem"); d.set_defaults(fn=cmd_doctor)
    return p


def main(argv=None):
    from .paths import PathError
    from .render import RenderError, SpecError
    from .theme import ThemeError
    a = build_parser().parse_args(argv)
    try: return a.fn(a)
    except (SpecError, RenderError, PathError, ThemeError, RuntimeError, OSError, json.JSONDecodeError) as e:
        print(f"error: {e}", file=sys.stderr); return 1
    except KeyboardInterrupt:
        print("\ncancelled", file=sys.stderr); return 130


if __name__ == "__main__":
    sys.exit(main())
