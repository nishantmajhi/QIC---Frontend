"""
fakemanim.py — a stand-in for the `manim` package.

`factorize.py` does `from manim import *` at import time, so nothing in it can
be imported — let alone run — without the real Manim, which is a large install
with native dependencies. This module provides just enough of Manim's surface
for the scene to be constructed and played, and records what it was asked to
draw instead of drawing it.

That makes the strings the video shows assertable: a test constructs the
scene, calls `construct()`, and reads back the text that reached the screen
rather than the variables behind it.

Install it with `install()` before importing `factorize`:

    import fakemanim
    fakemanim.install()
    import factorize
"""

import sys
import types


class Mobject:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.target = None

    def move_to(self, *_a, **_k):
        return self

    def next_to(self, *_a, **_k):
        return self

    def scale(self, *_a, **_k):
        return self

    def shift(self, *_a, **_k):
        return self

    def set_color(self, *_a, **_k):
        return self

    def to_edge(self, *_a, **_k):
        return self

    def get_center(self):
        return 0.0


class Text(Mobject):
    def __init__(self, text="", **kwargs):
        super().__init__(text, **kwargs)
        self.text = text
        self.font_size = kwargs.get("font_size")
        self.color = kwargs.get("color")

    def __repr__(self):
        return f"Text({self.text!r})"


class MathTex(Text):
    pass


class Tex(Text):
    pass


class Underline(Mobject):
    pass


class Line(Mobject):
    pass


class VGroup(Mobject):
    def __init__(self, *mobjects, **kwargs):
        super().__init__(*mobjects, **kwargs)
        self.mobjects = list(mobjects)


class _Animation(Mobject):
    """Write / FadeIn / FadeOut / ReplacementTransform all land here."""

    def __init__(self, *mobjects, **kwargs):
        super().__init__(*mobjects, **kwargs)
        self.mobjects = list(mobjects)
        self.name = type(self).__name__


class Write(_Animation):
    pass


class FadeIn(_Animation):
    pass


class FadeOut(_Animation):
    pass


class Create(_Animation):
    pass


class Transform(_Animation):
    pass


class ReplacementTransform(_Animation):
    pass


class _Camera:
    def __init__(self):
        self.background_color = None


class Scene:
    """Records animations instead of rendering them."""

    def __init__(self, *_a, **_k):
        self.camera = _Camera()
        self.recorded = []      # list of (animation-name, [text, ...])
        self.waits = []
        self.mobjects = []
        self.setup()

    def setup(self):
        pass

    def construct(self):
        pass

    def play(self, *anims, **_kwargs):
        for anim in anims:
            texts = []
            for m in getattr(anim, "mobjects", []):
                texts.extend(_texts_of(m))
            self.recorded.append((getattr(anim, "name", type(anim).__name__), texts))

    def wait(self, duration=1.0, **_kwargs):
        self.waits.append(duration)

    def add(self, *mobjects):
        self.mobjects.extend(mobjects)

    def remove(self, *mobjects):
        for m in mobjects:
            if m in self.mobjects:
                self.mobjects.remove(m)

    # ── Readback helpers used by the tests ────────────────────────────────

    def shown(self):
        """Every string the scene drew, in order, with duplicates kept."""
        out = []
        for name, texts in self.recorded:
            if name == "FadeOut":
                continue
            out.extend(texts)
        return out

    def faded(self):
        out = []
        for name, texts in self.recorded:
            if name == "FadeOut":
                out.extend(texts)
        return out


def _texts_of(m):
    if isinstance(m, Text):
        return [m.text]
    if isinstance(m, VGroup):
        out = []
        for child in m.mobjects:
            out.extend(_texts_of(child))
        return out
    return []


# Direction constants: factorize.py only ever multiplies them by a float.
UP = 1.0
DOWN = -1.0
LEFT = -1.0
RIGHT = 1.0
ORIGIN = 0.0
WHITE = "#FFFFFF"
BLACK = "#000000"
RED = "#FF0000"
GREEN = "#00FF00"
BLUE = "#0000FF"
YELLOW = "#FFFF00"


def install(module_name="manim"):
    """Register this module as `manim` in sys.modules."""
    mod = types.ModuleType(module_name)
    for key, value in globals().items():
        if not key.startswith("_") and key != "install":
            setattr(mod, key, value)
    mod.__all__ = [k for k in vars(mod) if not k.startswith("_")]
    sys.modules[module_name] = mod
    return mod
