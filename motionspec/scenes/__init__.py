"""Scene registry. A scene is `draw(c, t, s)` (c: Canvas, t: local seconds, s: the scene dict) plus optional sound cues
and a field schema used by `validate`. Register with @scene; load project scenes with `load_plugins`.

    from motionspec.scenes import scene

    @scene("badge", fields={"text": (str, True)}, cues=lambda s: [(0.1, "pop")])
    def badge(c, t, s):
        c.rect((100, 100, 500, 220), "accent", radius=40)
        c.text(300, 130, s["text"], "bold", 60, "accent_text")
"""
import importlib.util
import os

REGISTRY = {}
COMMON = {"type": (str, True), "dur": ((int, float), True), "bg": (str, False), "gradient": (list, False),
          "say": (str, False), "id": (str, False), "camera": (dict, False), "transition": (str, False), "comment": (str, False), "backdrop": (str, False), "invert": (bool, False)}


def scene(name, fields=None, cues=None, desc=""):
    def deco(fn):
        REGISTRY[name] = {"draw": fn, "cues": cues or (lambda s: []), "fields": fields or {}, "desc": desc or (fn.__doc__ or "").strip()}
        return fn
    return deco


def load_builtin():
    from . import brand, data, media, text, verbs  # noqa: F401  (import registers the scenes)


def load_plugins(paths):
    """Import every .py file in each path (a file or a directory) so its @scene decorators register."""
    for p in paths or []:
        files = [os.path.join(p, f) for f in sorted(os.listdir(p)) if f.endswith(".py")] if os.path.isdir(p) else [p]
        for f in files:
            spec = importlib.util.spec_from_file_location("motionspec_plugin_" + os.path.splitext(os.path.basename(f))[0], f)
            mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
