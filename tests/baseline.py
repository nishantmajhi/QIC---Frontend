"""
baseline.py — import the project as it was before this pass.

Every regression test in this suite has a counterpart in test_original.py
that asserts the defect is present in the original code. Nothing is
transcribed: the original files are read out of the repository's first commit
with `git show`, written to a scratch directory and imported from there, so
the assertions cannot drift from the code they describe.

`factorize.py` does `from manim import *`, so fakemanim has to be installed
before the baseline copy of it is imported.
"""

import atexit
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

_cache = {}
_scratch = None


def _first_commit() -> str:
    return subprocess.check_output(
        ["git", "rev-list", "--max-parents=0", "HEAD"],
        cwd=ROOT, text=True,
    ).strip().splitlines()[0]


def _scratch_dir() -> str:
    global _scratch
    if _scratch is None:
        _scratch = tempfile.mkdtemp(prefix="qic_baseline_")
        atexit.register(cleanup)
    return _scratch


def cleanup():
    """Remove the scratch copies. Registered with atexit as well, so that a
    module run on its own tidies up; run.py calls it directly before checking
    that the suite left nothing in the temp folder."""
    global _scratch
    if _scratch is not None:
        shutil.rmtree(_scratch, ignore_errors=True)
        _scratch = None


def source(filename: str) -> str:
    """The text of a file as it was in the first commit."""
    key = ("src", filename)
    if key not in _cache:
        _cache[key] = subprocess.check_output(
            ["git", "show", f"{_first_commit()}:{filename}"],
            cwd=ROOT,
        ).decode("utf-8")
    return _cache[key]


def module(filename: str, module_name: str):
    """Import a first-commit file under a name of its own."""
    if module_name in _cache:
        return _cache[module_name]

    path = os.path.join(_scratch_dir(), filename)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(source(filename))

    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    spec = importlib.util.spec_from_file_location(module_name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    _cache[module_name] = mod
    return mod
