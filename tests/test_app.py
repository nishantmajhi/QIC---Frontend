"""
test_app.py — the desktop app: the render pipeline, the temp files it owns,
and the messages it puts on the status line.

The worker methods are driven against a stand-in (appstub.py) so the pipeline
can be tested without a window. The tests that need real widgets build a real
MainApp and withdraw it before it can appear.
"""

import os
import shutil
import sys
import tempfile
import time
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app
import appstub
import factorsteps as F


def temp_media_dirs():
    root = tempfile.gettempdir()
    try:
        names = os.listdir(root)
    except OSError:
        return []
    return [os.path.join(root, n) for n in names if n.startswith("qic_manim_")]


class FakeProcess:
    """A Manim that has already finished, with a media directory to match."""

    def __init__(self, cmd, returncode=0, write="scene"):
        self.returncode = returncode
        self.terminated = False
        self._write = write
        self._media_dir = cmd[cmd.index("--media_dir") + 1]

    def communicate(self):
        if self._write:
            out = os.path.join(self._media_dir, "videos", "factorize", "480p15")
            partials = os.path.join(out, "partial_movie_files", "FactorizationScene")
            os.makedirs(partials, exist_ok=True)
            for i in range(27):
                with open(os.path.join(partials, f"part{i}.mp4"), "wb") as fh:
                    fh.write(b"\x00")
            if self._write == "scene":
                with open(os.path.join(out, "FactorizationScene.mp4"), "wb") as fh:
                    fh.write(b"\x00" * 64)
        return "rendered\n", "" if self.returncode == 0 else "Traceback: boom\n"

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated = True


def fake_manim(returncode=0, write="scene", record=None):
    """A stand-in for `subprocess` whose Popen() is a finished Manim."""

    def popen(cmd, **_kwargs):
        proc = FakeProcess(cmd, returncode, write)
        if record is not None:
            record.append(proc)
        return proc

    import subprocess as real
    return types.SimpleNamespace(Popen=popen, PIPE=real.PIPE, run=real.run)


class RenderPipelineTest(unittest.TestCase):
    """Base class: isolate the video directory and the scratch directories."""

    def setUp(self):
        self.videos = tempfile.mkdtemp(prefix="qic_testvideos_")
        self._real_video_dir = app.video_dir
        app.video_dir = lambda: self.videos
        self._real_subprocess = app.subprocess
        self.media_before = set(temp_media_dirs())

    def tearDown(self):
        app.video_dir = self._real_video_dir
        app.subprocess = self._real_subprocess
        shutil.rmtree(self.videos, ignore_errors=True)
        for path in set(temp_media_dirs()) - self.media_before:
            shutil.rmtree(path, ignore_errors=True)

    def new_media_dirs(self):
        return set(temp_media_dirs()) - self.media_before


class TheScratchDirectory(RenderPipelineTest):
    """The P1: Manim's media directory is deleted, the video is not."""

    def test_a_successful_render_leaves_no_scratch_directory(self):
        stub = appstub.FakeApp(app.MainApp)
        app.subprocess = fake_manim()
        app.MainApp._render(stub, 2, 7, 3, "ql")

        self.assertEqual(stub.failed, [])
        self.assertEqual(len(stub.done), 1)
        self.assertEqual(self.new_media_dirs(), set())

    def test_a_failed_render_leaves_no_scratch_directory(self):
        stub = appstub.FakeApp(app.MainApp)
        app.subprocess = fake_manim(returncode=1, write=False)
        app.MainApp._render(stub, 2, 7, 3, "ql")

        self.assertEqual(stub.done, [])
        self.assertEqual(len(stub.failed), 1)
        self.assertIn("boom", stub.failed[0])
        self.assertEqual(self.new_media_dirs(), set())

    def test_the_video_survives_in_a_directory_the_app_owns(self):
        stub = appstub.FakeApp(app.MainApp)
        app.subprocess = fake_manim()
        app.MainApp._render(stub, 2, 7, 3, "ql")

        video = stub.done[0]
        self.assertTrue(os.path.isfile(video))
        self.assertEqual(os.path.dirname(video), self.videos)
        self.assertEqual(os.path.getsize(video), 64)
        self.assertTrue(video.endswith(".mp4"))

    def test_two_renders_leave_two_videos_and_no_scratch(self):
        app.subprocess = fake_manim()
        for a, b, c in [(2, 7, 3), (1, -5, 6)]:
            stub = appstub.FakeApp(app.MainApp)
            app.MainApp._render(stub, a, b, c, "ql")
            time.sleep(0.01)
        self.assertEqual(len(os.listdir(self.videos)), 2)
        self.assertEqual(self.new_media_dirs(), set())

    def test_the_config_file_is_removed_too(self):
        stub = appstub.FakeApp(app.MainApp)
        captured = {}

        base = fake_manim()

        def popen(cmd, env=None, **kwargs):
            captured["cfg"] = env["QIC_FACTOR_CONFIG"]
            captured["existed"] = os.path.isfile(captured["cfg"])
            return base.Popen(cmd, env=env, **kwargs)

        app.subprocess = types.SimpleNamespace(
            Popen=popen, PIPE=base.PIPE, run=base.run)
        app.MainApp._render(stub, 2, 7, 3, "ql")

        self.assertTrue(captured["existed"])
        self.assertFalse(os.path.exists(captured["cfg"]))


class TheWorkerThread(RenderPipelineTest):
    """Anything raised in the worker has to reach the UI, or it stays locked."""

    def test_a_failure_to_start_the_renderer_is_reported_not_raised(self):
        stub = appstub.FakeApp(app.MainApp)

        def explode(*_a, **_k):
            raise OSError(8, "Exec format error")

        import subprocess as real
        app.subprocess = types.SimpleNamespace(
            Popen=explode, PIPE=real.PIPE, run=real.run)

        app.MainApp._render(stub, 2, 7, 3, "ql")   # must not raise

        self.assertEqual(len(stub.failed), 1)
        self.assertIn("could not be started", stub.failed[0])
        self.assertIn("Exec format error", stub.failed[0])

    def test_the_scratch_directory_goes_even_when_the_worker_throws(self):
        stub = appstub.FakeApp(app.MainApp)
        base = fake_manim()

        def popen(cmd, **kwargs):
            base.Popen(cmd, **kwargs).communicate()
            raise RuntimeError("after the render")

        import subprocess as real
        app.subprocess = types.SimpleNamespace(
            Popen=popen, PIPE=real.PIPE, run=real.run)

        app.MainApp._render(stub, 2, 7, 3, "ql")

        self.assertEqual(len(stub.failed), 1)
        self.assertEqual(self.new_media_dirs(), set())

    def test_a_render_that_produces_nothing_is_reported(self):
        stub = appstub.FakeApp(app.MainApp)
        app.subprocess = fake_manim(returncode=0, write=False)
        app.MainApp._render(stub, 2, 7, 3, "ql")

        self.assertEqual(stub.done, [])
        self.assertIn("no video file was produced", stub.failed[0])


class TheRendererLifetime(RenderPipelineTest):
    """Closing the window has to take the renderer with it."""

    def test_the_running_renderer_is_terminated_on_close(self):
        started = []
        stub = appstub.FakeApp(app.MainApp)
        app.subprocess = fake_manim(record=started)
        stub.render(2, 7, 3, "ql")

        self.assertEqual(len(started), 1)
        proc = started[0]
        proc.returncode = None          # pretend it is still going

        stub._proc = proc
        stub._root = _RecordingRoot()
        app.MainApp._on_close(stub)

        self.assertTrue(proc.terminated)
        self.assertTrue(stub._closing)
        self.assertTrue(stub._root.destroyed)

    def test_closing_with_no_render_running_just_closes(self):
        stub = appstub.FakeApp(app.MainApp)
        stub._root = _RecordingRoot()
        app.MainApp._on_close(stub)
        self.assertTrue(stub._root.destroyed)

    def test_a_result_is_not_delivered_to_a_window_that_has_gone(self):
        stub = appstub.FakeApp(app.MainApp)
        app.subprocess = fake_manim()
        stub._closing = True
        stub.render(2, 7, 3, "ql")

        # No callback into a destroyed Tk, and no scratch directory either.
        self.assertEqual(stub.done, [])
        self.assertEqual(stub.failed, [])
        self.assertEqual(self.new_media_dirs(), set())


class _RecordingRoot:
    def __init__(self):
        self.destroyed = False

    def destroy(self):
        self.destroyed = True

    def after(self, _delay, func=None, *args):
        if func is not None:
            func(*args)


class TheVideoSearch(unittest.TestCase):

    def setUp(self):
        self.media = tempfile.mkdtemp(prefix="qic_search_")
        self.out = os.path.join(self.media, "videos", "factorize", "480p15")
        self.partials = os.path.join(self.out, "partial_movie_files",
                                     "FactorizationScene")
        os.makedirs(self.partials)

    def tearDown(self):
        shutil.rmtree(self.media, ignore_errors=True)

    def write(self, path, name):
        full = os.path.join(path, name)
        with open(full, "wb") as fh:
            fh.write(b"\x00")
        return full

    def test_it_finds_the_combined_file(self):
        self.write(self.partials, "part0.mp4")
        scene = self.write(self.out, "FactorizationScene.mp4")
        self.assertEqual(app._find_video(self.media), scene)

    def test_it_refuses_to_offer_a_fragment(self):
        self.write(self.partials, "part0.mp4")
        self.assertIsNone(app._find_video(self.media))

    def test_it_finds_nothing_in_an_empty_directory(self):
        self.assertIsNone(app._find_video(self.media))


class TheVideoSweep(unittest.TestCase):

    def setUp(self):
        self.videos = tempfile.mkdtemp(prefix="qic_sweep_")
        self._real = app.video_dir
        app.video_dir = lambda: self.videos

    def tearDown(self):
        app.video_dir = self._real
        shutil.rmtree(self.videos, ignore_errors=True)

    def make(self, name, age_s):
        path = os.path.join(self.videos, name)
        with open(path, "wb") as fh:
            fh.write(b"\x00")
        stamp = time.time() - age_s
        os.utime(path, (stamp, stamp))
        return path

    def test_it_removes_yesterdays_videos(self):
        old = self.make("factorization_old.mp4", 48 * 3600)
        self.assertEqual(app.sweep_old_videos(), 1)
        self.assertFalse(os.path.exists(old))

    def test_it_keeps_a_video_from_this_session(self):
        fresh = self.make("factorization_new.mp4", 60)
        self.assertEqual(app.sweep_old_videos(), 0)
        self.assertTrue(os.path.exists(fresh))

    def test_it_leaves_everything_that_is_not_a_video_alone(self):
        other = self.make("notes.txt", 48 * 3600)
        self.assertEqual(app.sweep_old_videos(), 0)
        self.assertTrue(os.path.exists(other))

    def test_the_real_video_directory_is_created_on_demand(self):
        app.video_dir = self._real
        path = app.video_dir()
        self.assertTrue(os.path.isdir(path))
        self.assertEqual(os.path.basename(path), "qic-frontend-videos")


class TheParseErrorMessages(unittest.TestCase):

    def test_every_error_the_library_can_return_has_a_message(self):
        self.assertEqual(sorted(app._PARSE_ERRORS), [1, 2, 3, 4, 5, 6])

    def test_the_messages_are_distinct_and_say_something(self):
        messages = list(app._PARSE_ERRORS.values())
        self.assertEqual(len(messages), len(set(messages)))
        for message in messages:
            self.assertGreater(len(message), 20)

    def test_the_not_quadratic_message_names_the_problem(self):
        self.assertIn("quadratic", app._PARSE_ERRORS[4].lower())
        self.assertIn("range", app._PARSE_ERRORS[5].lower())


class TheManimCheck(unittest.TestCase):

    def test_it_agrees_with_the_interpreter_that_runs_the_renderer(self):
        # Asked in a subprocess on purpose: this process has fakemanim
        # registered as `manim`, and the question the app needs answered is
        # what `sys.executable -m manim` will do, not what is in sys.modules.
        import subprocess

        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        answer = subprocess.run(
            [sys.executable, "-c",
             f"import sys; sys.path.insert(0, {root!r}); "
             "import app; print(app.manim_available())"],
            capture_output=True, text=True,
        )
        self.assertEqual(answer.returncode, 0, answer.stderr)

        probe = subprocess.run(
            [sys.executable, "-c", "import manim"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        self.assertEqual(answer.stdout.strip(), str(probe.returncode == 0))


# ── Tests that need real widgets ─────────────────────────────────────────────

class _already_destroyed:
    """Stands in for a destroyed root so tearDown can call destroy() again."""

    def destroy(self):
        pass


def tk_available():
    try:
        import tkinter
        root = tkinter.Tk()
        root.destroy()
        return True
    except Exception:
        return False


@unittest.skipUnless(tk_available(), "no display for Tk")
class TheWindow(unittest.TestCase):

    def setUp(self):
        self.dialogs = []
        self._real_dialog = app.ErrorDialog
        self._real_parse = app.parse
        self._real_open = app._open_file
        app.ErrorDialog = lambda parent, title, detail, t: self.dialogs.append(
            (title, detail))
        self.window = app.MainApp()
        self.window._root.withdraw()

    def tearDown(self):
        app.ErrorDialog = self._real_dialog
        app.parse = self._real_parse
        app._open_file = self._real_open
        self.window._root.destroy()

    def status(self):
        return self.window._status_var.get()

    def type_in(self, text):
        self.window._placeholder_active = False
        self.window._entry.configure(state="normal")
        self.window._entry.delete(0, "end")
        self.window._entry.insert(0, text)

    def stub_parse(self, a=0, b=0, c=0, error=0):
        result = types.SimpleNamespace(a=a, b=b, c=c, error=error)
        app.parse = lambda _eq: result

    def test_the_placeholder_is_not_submitted_as_an_equation(self):
        self.window._on_go()
        self.assertIn("not found", self.status())

    def test_an_empty_entry_is_refused(self):
        self.type_in("   ")
        self.window._on_go()
        self.assertIn("not found", self.status())

    def test_each_library_error_reaches_the_status_line(self):
        for code, message in app._PARSE_ERRORS.items():
            self.stub_parse(error=code)
            self.type_in("2x^2+7x+3")
            self.window._on_go()
            self.assertEqual(self.status(), message, code)

    def test_an_unknown_error_code_still_says_something(self):
        self.stub_parse(error=99)
        self.type_in("2x^2+7x+3")
        self.window._on_go()
        self.assertIn("Parse error", self.status())

    def test_a_missing_library_is_reported_rather_than_raised(self):
        def missing(_eq):
            raise FileNotFoundError("Cannot find 'libqic.dll'.")

        app.parse = missing
        self.type_in("2x^2+7x+3")
        self.window._on_go()
        self.assertIn("libqic", self.status())

    def test_resizing_survives_the_window_being_torn_down(self):
        # A <Configure> event arrives after the widgets are destroyed when
        # the app closes, and the handler used to raise out of a Tk callback.
        self.window._root.destroy()
        self.window._on_resize()
        self.window._root = _already_destroyed()   # for tearDown

    def test_resizing_adjusts_the_entry_and_the_progress_bar(self):
        self.window._root.geometry("900x600")
        self.window._root.update_idletasks()
        self.window._on_resize()
        width = int(self.window._progress_canvas.cget("width"))
        self.assertEqual(width, self.window._clamp_input_w(
            self.window._root.winfo_width()))

    def test_the_window_unlocks_after_a_failed_render(self):
        self.window._lock()
        self.window._on_fail("something went wrong")
        self.assertEqual(str(self.window._go_btn.cget("state")), "normal")
        self.assertEqual(str(self.window._entry.cget("state")), "normal")
        self.assertEqual(len(self.dialogs), 1)

    def test_a_video_that_cannot_be_opened_is_still_reported(self):
        def refuse(_path):
            raise OSError(1155, "No application is associated")

        app._open_file = refuse
        self.window._lock()
        self.window._on_done(r"C:\videos\factorization.mp4")

        self.assertEqual(str(self.window._go_btn.cget("state")), "normal")
        self.assertIn("Render complete", self.status())
        self.assertEqual(len(self.dialogs), 1)
        self.assertIn("factorization.mp4", self.dialogs[0][1])

    def test_the_video_is_opened_when_it_can_be(self):
        opened = []
        app._open_file = opened.append
        self.window._lock()
        self.window._on_done(r"C:\videos\factorization.mp4")

        self.assertEqual(opened, [r"C:\videos\factorization.mp4"])
        self.assertIn("opening video", self.status())
        self.assertEqual(self.dialogs, [])

    def test_without_manim_the_working_is_shown_as_text(self):
        self.stub_parse(a=2, b=7, c=3)
        real_check = app.manim_available
        app.manim_available = lambda: False
        try:
            self.type_in("2x^2+7x+3")
            self.window._on_go()
        finally:
            app.manim_available = real_check

        self.assertEqual(len(self.dialogs), 1)
        title, detail = self.dialogs[0]
        self.assertIn("no renderer", title.lower())
        self.assertIn(F.plan(2, 7, 3)["final"], detail)
        self.assertIn("pip install", detail)
        # and the window is usable again
        self.assertEqual(str(self.window._go_btn.cget("state")), "normal")


if __name__ == "__main__":
    unittest.main()
