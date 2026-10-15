"""
scenerun.py — run a FactorizationScene against the fake Manim and read back
the strings it drew.

The point of doing it this way is that assertions are made against what
reaches the screen rather than against the variables behind it. Two of the
defects this suite pins were in code whose arithmetic was right and whose
output was wrong.
"""

import json
import os
import tempfile

import fakemanim

fakemanim.install()


def run(scene_module, a, b, c):
    """Play scene_module.FactorizationScene for a, b, c; return the scene."""
    fd, cfg_path = tempfile.mkstemp(suffix=".json", prefix="qic_scenerun_")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump({"a": a, "b": b, "c": c}, fh)

    previous = os.environ.get("QIC_FACTOR_CONFIG")
    os.environ["QIC_FACTOR_CONFIG"] = cfg_path
    try:
        scene = scene_module.FactorizationScene()
        scene.construct()
        return scene
    finally:
        if previous is None:
            os.environ.pop("QIC_FACTOR_CONFIG", None)
        else:
            os.environ["QIC_FACTOR_CONFIG"] = previous
        os.unlink(cfg_path)


def lines(scene_module, a, b, c):
    """Every non-empty string the scene drew, in order."""
    return [t for t in run(scene_module, a, b, c).shown() if t.strip()]
