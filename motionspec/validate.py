"""Spec validation with precise paths and suggestions, plus JSON Schema export for editors and LLMs."""
import difflib

from .constants import SPEC_VERSION
from .layout import FORMATS
from .scenes import COMMON, REGISTRY, load_builtin

TOP = {"spec_version": (int, False), "id": (str, False), "kind": (str, False), "format": (str, False), "theme": ((str, dict), False),
       "scenes": (list, True), "captions": (list, False), "voiceover": (str, False), "music": ((str, dict), False), "facts": (list, False),
       "policy": (str, False), "autotime": (bool, False), "blur": (int, False), "post": (dict, False), "fps": (int, False),
       "sfx": (bool, False), "comment": (str, False)}
KINDS = ("reel", "ad", "explainer", "demo", "general")
MAX_DUR, MAX_TOTAL = 600, 1800


def _suggest(word, options):
    m = difflib.get_close_matches(str(word), list(options), n=1, cutoff=0.6)
    return f" Did you mean '{m[0]}'?" if m else ""


def _type_ok(v, types):
    types = types if isinstance(types, tuple) else (types,)
    if isinstance(v, bool): return bool in types                     # a bool is not a number
    return isinstance(v, types)


def _tname(types):
    types = types if isinstance(types, tuple) else (types,)
    return "/".join({"int": "number", "float": "number", "str": "text", "dict": "object", "list": "list", "bool": "true/false"}.get(x.__name__, x.__name__) for x in types)


def validate(spec):
    """Returns a list of error strings like "scenes[2] (bars).items: required"; empty list means valid."""
    load_builtin(); errs = []
    if not isinstance(spec, dict): return ["spec must be a JSON object"]
    for k, v in spec.items():
        if k not in TOP: errs.append(f"{k}: unknown top-level key.{_suggest(k, TOP)}"); continue
        if not _type_ok(v, TOP[k][0]): errs.append(f"{k}: expected {_tname(TOP[k][0])}, got {type(v).__name__}")
    for k, (_, req) in TOP.items():
        if req and k not in spec: errs.append(f"{k}: required")
    if spec.get("spec_version", SPEC_VERSION) > SPEC_VERSION: errs.append(f"spec_version {spec['spec_version']} is newer than this engine ({SPEC_VERSION}); upgrade motionspec")
    fmt = spec.get("format", "reel")
    if isinstance(fmt, str) and fmt not in FORMATS and "x" not in fmt: errs.append(f"format: unknown '{fmt}'.{_suggest(fmt, FORMATS)} Presets: {sorted(FORMATS)} or WIDTHxHEIGHT")
    if spec.get("kind") and spec["kind"] not in KINDS: errs.append(f"kind: '{spec['kind']}' not one of {KINDS}")
    scenes = spec.get("scenes")
    if isinstance(scenes, list):
        if not scenes: errs.append("scenes: needs at least one scene")
        total = 0.0
        for i, sc in enumerate(scenes):
            if not isinstance(sc, dict): errs.append(f"scenes[{i}]: must be an object"); continue
            typ = sc.get("type"); name = f"scenes[{i}]" + (f" ({typ})" if typ else "")
            if typ not in REGISTRY:
                errs.append(f"{name}.type: unknown scene.{_suggest(typ, REGISTRY)} Available: {sorted(REGISTRY)}"); continue
            fields = {**COMMON, **REGISTRY[typ]["fields"]}
            for k, v in sc.items():
                if k not in fields: errs.append(f"{name}.{k}: unknown field.{_suggest(k, fields)}"); continue
                if not _type_ok(v, fields[k][0]): errs.append(f"{name}.{k}: expected {_tname(fields[k][0])}, got {type(v).__name__}")
            for k, (_, req) in fields.items():
                if req and k not in sc: errs.append(f"{name}.{k}: required")
            d = sc.get("dur")
            if _type_ok(d, (int, float)):
                if not 0.3 <= d <= MAX_DUR: errs.append(f"{name}.dur: {d}s out of range (0.3 to {MAX_DUR})")
                else: total += d
            for key in ("items", "steps", "events", "lines", "series", "words"):
                if key in sc and isinstance(sc[key], list) and not sc[key]: errs.append(f"{name}.{key}: must not be empty")
            if typ == "grid" and _type_ok(sc.get("hit"), int) and _type_ok(sc.get("total"), int) and sc["hit"] > sc["total"]:
                errs.append(f"{name}.hit: {sc['hit']} is greater than total {sc['total']}")
            if typ == "chart":
                for j, ser in enumerate(sc.get("series") or []):
                    if not isinstance(ser, dict) or not isinstance(ser.get("values"), list) or not ser["values"]: errs.append(f"{name}.series[{j}].values: needs a non-empty list of numbers")
            if typ == "bars":
                for j, it in enumerate(sc.get("items") or []):
                    if not isinstance(it, dict) or not _type_ok(it.get("value"), (int, float)) or "label" not in it: errs.append(f"{name}.items[{j}]: needs label and numeric value")
                    elif it["value"] < 0: errs.append(f"{name}.items[{j}].value: negative values are not supported")
        if total > MAX_TOTAL: errs.append(f"scenes: total {total:.0f}s exceeds the {MAX_TOTAL}s limit")
    for j, cap in enumerate(spec.get("captions") or []):
        if not isinstance(cap, dict) or not all(k in cap for k in ("t0", "t1", "text")): errs.append(f"captions[{j}]: needs t0, t1, text")
        elif cap["t1"] <= cap["t0"]: errs.append(f"captions[{j}]: t1 must be after t0")
    return errs


def json_schema():
    """JSON Schema (draft-07) generated from the scene registry, for editor autocomplete and LLM grounding."""
    load_builtin()
    def js(types):
        types = types if isinstance(types, tuple) else (types,)
        m = {"int": "integer", "float": "number", "str": "string", "dict": "object", "list": "array", "bool": "boolean"}
        out = sorted({("number" if x is float or (x is int and len(types) > 1) else m[x.__name__]) for x in types})
        return {"type": out[0] if len(out) == 1 else out}
    variants = []
    for name, info in sorted(REGISTRY.items()):
        fields = {**COMMON, **info["fields"]}
        variants.append({"title": name, "description": info["desc"], "type": "object", "additionalProperties": False,
                         "required": [k for k, (_, r) in fields.items() if r],
                         "properties": {**{k: js(t) for k, (t, _) in fields.items()}, "type": {"const": name}}})
    return {"$schema": "http://json-schema.org/draft-07/schema#", "title": "motionspec", "type": "object", "required": ["scenes"],
            "properties": {**{k: js(t) for k, (t, _) in TOP.items()}, "format": {"type": "string", "description": "Preset or WIDTHxHEIGHT", "examples": sorted(FORMATS)},
                           "scenes": {"type": "array", "minItems": 1, "items": {"oneOf": variants}}}}
