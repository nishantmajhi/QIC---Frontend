"""
appstub.py — drive MainApp's worker methods without a window.

`_render` and `_on_done` touch only `self._root.after`, `self._t` and the two
status helpers, so they can be called as plain functions against a stand-in.
That keeps the tests for the render pipeline free of Tk, which matters because
the pipeline is what the P1 was in.

Tests that need real widgets build a real MainApp and withdraw it; see
test_app.py.
"""

import functools


class FakeRoot:
    """Tk's `after` without a Tk: run the callback immediately, and record it."""

    def __init__(self):
        self.calls = []

    def after(self, _delay, func=None, *args):
        if func is None:
            return "after#0"
        self.calls.append((getattr(func, "__name__", str(func)), args))
        func(*args)
        return "after#0"


class FakeApp:
    """
    Enough of MainApp for _render, _do_render and _on_done.

    Pass the MainApp class to borrow its methods: anything not defined here
    is looked up on that class and bound to this object, so `self._do_render`
    inside `_render` reaches the real implementation while `self._on_fail`
    reaches the recorder below.
    """

    def __init__(self, main_app_cls=None):
        self._cls = main_app_cls
        self._root = FakeRoot()
        self._proc = None
        self._closing = False
        self._t = {"OK": "#OK", "ERR": "#ERR", "INFO": "#INFO", "FG_DIM": "#DIM"}
        self.done = []      # video paths handed to _on_done
        self.failed = []    # detail strings handed to _on_fail
        self.status = []
        self.unlocked = 0
        self.opened = []

    def __getattr__(self, name):
        cls = self.__dict__.get("_cls")
        if cls is not None and hasattr(cls, name):
            return functools.partial(getattr(cls, name), self)
        raise AttributeError(name)

    def render(self, a, b, c, quality="ql"):
        """Run the borrowed class's worker, as the render thread would."""
        return self._cls._render(self, a, b, c, quality)

    # ── the parts of MainApp the worker calls back into ──────────────────

    def _on_done(self, path):
        self.done.append(path)

    def _on_fail(self, detail):
        self.failed.append(detail)

    def _unlock(self):
        self.unlocked += 1

    def _set_status(self, msg, color=None):
        self.status.append((msg, color))
