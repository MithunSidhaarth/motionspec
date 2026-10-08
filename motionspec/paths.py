"""Path sandbox. Specs and themes are data that may come from anywhere (including an LLM), so every file they name is
resolved against a root directory and rejected if it escapes it or is a URL. Set once per process with `configure`."""
import os
import re

_root = os.getcwd()
_allow_abs = False


class PathError(ValueError):
    """A spec referenced a file that is outside the project root, a URL, or missing."""


def configure(root, allow_abs=False):
    global _root, _allow_abs
    _root = os.path.abspath(root); _allow_abs = allow_abs


def resolve(path, what="file", must_exist=True):
    if not isinstance(path, str) or not path: raise PathError(f"{what}: empty path")
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]+://", path) or path.lower().startswith(("concat:", "file:", "pipe:", "subfile:")):
        raise PathError(f"{what}: URLs and ffmpeg protocols are not allowed ('{path}'). Download the file into the project first.")
    full = os.path.abspath(path if os.path.isabs(path) else os.path.join(_root, path))
    if not _allow_abs:
        try:
            inside = os.path.commonpath([full, _root]) == _root
        except ValueError:
            inside = False
        if not inside:
            raise PathError(f"{what}: '{path}' is outside the project root '{_root}'. Move it inside, or pass --allow-abs-paths.")
    if must_exist and not os.path.isfile(full):
        near = ""
        d = os.path.dirname(full)
        if os.path.isdir(d):
            import difflib
            m = difflib.get_close_matches(os.path.basename(full), os.listdir(d), n=1)
            near = f" Did you mean '{m[0]}'?" if m else ""
        raise PathError(f"{what}: file not found: {full}.{near}")
    return full
