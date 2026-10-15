"""
test_original.py — the defects this pass fixed, asserted against the code
that had them.

These tests fail if the original code stops being wrong, which is the point:
a regression test that has never been seen to fail is testing nothing. The
original is read out of the first commit, never transcribed — see baseline.py.

Every case here has a counterpart in the other test modules asserting the
fixed behaviour.
"""

import os
import shutil
import tempfile
import types
import unittest

import baseline
import fakemanim
import scenerun

fakemanim.install()

MINUS = "−"
HYPHEN = "-"


def original_factorize():
    return baseline.module("factorize.py", "original_factorize")


def original_app():
    return baseline.module("app.py", "original_app")


class TheEmptyGroupBracket(unittest.TestCase):
    """c = 0 made the middle-term method degenerate, and it showed."""

    def test_grouping_step_drew_an_empty_bracket(self):
        shown = scenerun.lines(original_factorize(), 1, 3, 0)
        self.assertTrue(
            any("() = 0" in line for line in shown),
            "expected the original to draw an empty group; got:\n"
            + "\n".join(shown),
        )

    def test_factoring_step_drew_a_term_worth_nothing(self):
        shown = scenerun.lines(original_factorize(), 1, 3, 0)
        self.assertTrue(
            any("0(" in line for line in shown),
            "expected the original to draw '+ 0(x + 3)'",
        )

    def test_split_step_changed_nothing_while_claiming_to_split(self):
        scene = scenerun.run(original_factorize(), 1, 3, 0)
        shown = [t for t in scene.shown() if t.strip()]
        step1 = shown.index("Step 1 — Split the Middle Term")
        # The equation drawn by the split step is identical to the one before
        # it: there is nothing to split when c is 0.
        self.assertEqual(shown[step1 + 1], shown[step1 + 2])

    def test_the_split_note_offered_a_zero_term(self):
        shown = scenerun.lines(original_factorize(), 1, 3, 0)
        self.assertTrue(any("0x)" in line for line in shown))


class TheDiscriminantSubstitution(unittest.TestCase):

    def test_a_negative_b_was_substituted_without_brackets(self):
        shown = scenerun.lines(original_factorize(), 1, -5, 6)
        disc = [l for l in shown if l.startswith("Check:")][0]
        # "-5² - 4 x 1 x 6 = 1" reads as -(5²) = -25 by the usual precedence,
        # and contradicts the 1 printed at the end of the same line.
        self.assertIn("-5²", disc)
        self.assertNotIn("(−5)", disc)

    def test_a_negative_c_was_substituted_without_brackets(self):
        shown = scenerun.lines(original_factorize(), 1, 0, -4)
        disc = [l for l in shown if l.startswith("Check:")][0]
        self.assertIn("× -4", disc)


class TheTwoMinusSigns(unittest.TestCase):
    """Generated maths mixed U+002D and U+2212 inside one frame."""

    def test_the_grouping_step_mixed_both_glyphs(self):
        shown = scenerun.lines(original_factorize(), 1, -5, 6)
        grouped = [l for l in shown if l.startswith("(x")][0]
        self.assertIn(HYPHEN, grouped)
        self.assertIn(MINUS, grouped)

    def test_the_split_note_used_the_hyphen(self):
        shown = scenerun.lines(original_factorize(), 1, -5, 6)
        note = [l for l in shown if l.startswith("Rewrite")][0]
        self.assertIn("'-5x'", note)


class TheStepOneNote(unittest.TestCase):

    def test_it_quoted_a_term_that_was_never_on_screen(self):
        shown = scenerun.lines(original_factorize(), 1, 0, -4)
        equation = [l for l in shown if l.startswith("x²")][0]
        note = [l for l in shown if l.startswith("Rewrite")][0]
        self.assertNotIn("0x", equation)     # the equation reads x² − 4 = 0
        self.assertIn("'0x'", note)          # the note talks about '0x'

    def test_it_spelled_unit_coefficients_with_a_one(self):
        shown = scenerun.lines(original_factorize(), 1, -2, 1)
        note = [l for l in shown if l.startswith("Rewrite")][0]
        self.assertIn("-1x", note)           # the equation shows "− x"


class TheParseErrorTable(unittest.TestCase):
    """The table was written against a four-value enum that now has seven."""

    def test_codes_four_to_six_had_no_message(self):
        table = original_app()._PARSE_ERRORS
        self.assertEqual(sorted(table), [1, 2, 3])
        for code in (4, 5, 6):
            self.assertIsNone(table.get(code))


class TheTempDirectoryLeak(unittest.TestCase):
    """The P1: a Manim media directory per render, kept for ever."""

    def setUp(self):
        self.app_mod = original_app()
        self.before = set(_temp_media_dirs())

    def tearDown(self):
        for path in set(_temp_media_dirs()) - self.before:
            shutil.rmtree(path, ignore_errors=True)

    def test_the_media_directory_survived_a_successful_render(self):
        import appstub

        stub = appstub.FakeApp(self.app_mod.MainApp)
        with _fake_manim_run(self.app_mod, returncode=0, write_video=True):
            self.app_mod.MainApp._render(stub, 2, 7, 3, "ql")

        self.assertEqual(len(stub.done), 1, stub.failed)
        video = stub.done[0]
        # The original handed the UI a path inside the scratch directory and
        # left the whole directory — 46 files for a 480p render — behind.
        self.assertTrue(os.path.isfile(video))
        self.assertIn("qic_manim_", video)
        self.assertEqual(len(set(_temp_media_dirs()) - self.before), 1)

    def test_the_media_directory_survived_a_failed_render(self):
        import appstub

        stub = appstub.FakeApp(self.app_mod.MainApp)
        with _fake_manim_run(self.app_mod, returncode=1, write_video=False):
            self.app_mod.MainApp._render(stub, 2, 7, 3, "ql")

        self.assertEqual(len(stub.done), 0)
        self.assertEqual(len(set(_temp_media_dirs()) - self.before), 1)


class TheLockedWindow(unittest.TestCase):

    def test_an_exception_in_the_worker_escaped_the_thread(self):
        import appstub

        app_mod = original_app()
        stub = appstub.FakeApp(app_mod.MainApp)
        before = set(_temp_media_dirs())

        def explode(*_a, **_k):
            raise OSError(8, "Exec format error")

        original_run = app_mod.subprocess
        app_mod.subprocess = _subprocess_shim(explode)
        try:
            # Nothing catches this. In the real app it ends the daemon thread
            # with the window still locked and the progress bar still moving.
            with self.assertRaises(OSError):
                app_mod.MainApp._render(stub, 2, 7, 3, "ql")
        finally:
            app_mod.subprocess = original_run

        self.assertEqual(stub.failed, [])
        self.assertEqual(stub.unlocked, 0)

        # The original leaked the scratch directory on this path too, which
        # is the P1 again: clean up after it rather than leaving it here.
        for path in set(_temp_media_dirs()) - before:
            shutil.rmtree(path, ignore_errors=True)


class TheAbandonedRenderer(unittest.TestCase):
    """Closing the app left Manim rendering a video nobody would collect."""

    def test_there_was_no_handle_on_the_renderer_and_no_close_handler(self):
        source = baseline.source("app.py")
        # subprocess.run hands back a process that has already finished, so
        # there was no handle to terminate even if something had wanted to,
        # and nothing was watching for the window closing either.
        self.assertIn("subprocess.run(", source)
        self.assertNotIn("terminate", source)
        self.assertNotIn("WM_DELETE_WINDOW", source)


class ThePartialMovieFiles(unittest.TestCase):

    def test_a_partial_movie_file_could_be_offered_as_the_video(self):
        import appstub

        app_mod = original_app()
        stub = appstub.FakeApp(app_mod.MainApp)
        before = set(_temp_media_dirs())
        try:
            # Manim exits 0 but the combine step left nothing behind: only the
            # per-animation fragments exist. The original took the first .mp4
            # os.walk handed it and opened a one-second fragment.
            with _fake_manim_run(app_mod, returncode=0, write_video="partials"):
                app_mod.MainApp._render(stub, 2, 7, 3, "ql")

            self.assertEqual(len(stub.done), 1, stub.failed)
            self.assertIn("partial_movie_files", stub.done[0])
        finally:
            for path in set(_temp_media_dirs()) - before:
                shutil.rmtree(path, ignore_errors=True)


# ── helpers ──────────────────────────────────────────────────────────────────

def _temp_media_dirs():
    root = tempfile.gettempdir()
    try:
        names = os.listdir(root)
    except OSError:
        return []
    return [os.path.join(root, n) for n in names if n.startswith("qic_manim_")]


def _subprocess_shim(run):
    """A stand-in for the `subprocess` module holding just what _render uses."""
    import subprocess as real

    return types.SimpleNamespace(run=run, PIPE=real.PIPE, Popen=real.Popen)


class _fake_manim_run:
    """Swap a module's `subprocess` for one whose run() writes a video."""

    def __init__(self, module, returncode=0, write_video=True):
        self.module = module
        self.returncode = returncode
        self.write_video = write_video
        self.original = None

    def __enter__(self):
        self.original = self.module.subprocess
        returncode, write_video = self.returncode, self.write_video

        class Completed:
            def __init__(self, rc):
                self.returncode = rc
                self.stdout = "rendered\n"
                self.stderr = "" if rc == 0 else "boom\n"

        def fake_run(cmd, **_kwargs):
            media_dir = cmd[cmd.index("--media_dir") + 1]
            if write_video:
                out = os.path.join(media_dir, "videos", "factorize", "480p15")
                partials = os.path.join(out, "partial_movie_files",
                                        "FactorizationScene")
                os.makedirs(partials, exist_ok=True)
                for i in range(3):
                    with open(os.path.join(partials, f"part{i}.mp4"), "wb") as fh:
                        fh.write(b"\x00")
                if write_video != "partials":
                    scene_file = os.path.join(out, "FactorizationScene.mp4")
                    with open(scene_file, "wb") as fh:
                        fh.write(b"\x00" * 16)
            return Completed(returncode)

        self.module.subprocess = _subprocess_shim(fake_run)
        return self

    def __exit__(self, *_exc):
        self.module.subprocess = self.original
        return False


if __name__ == "__main__":
    unittest.main()
