"""
test_render.py — one real render, end to end.

Everything else in this suite replaces Manim with a stand-in, which is what
makes the rest of the suite fast enough to run on every change. This module
runs the real thing once: the app's own worker, the real `python -m manim`,
the real ffmpeg, and then checks that the MP4 exists, that it is a video, and
that nothing was left in the temp folder.

It is skipped when the interpreter running the tests cannot import Manim.
Install it with `pip install -r requirements.txt` and make sure FFmpeg is on
PATH; the render takes about a minute.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app
import appstub


def real_manim_present():
    # Asked in a subprocess because this process may have tests/fakemanim.py
    # registered as `manim`.
    probe = subprocess.run(
        [sys.executable, "-c", "import manim"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return probe.returncode == 0


def ffmpeg_present():
    return shutil.which("ffmpeg") is not None


@unittest.skipUnless(real_manim_present(), "manim is not installed for this python")
@unittest.skipUnless(ffmpeg_present(), "ffmpeg is not on PATH")
class ARealRender(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.videos = tempfile.mkdtemp(prefix="qic_realvideos_")
        cls._real_video_dir = app.video_dir
        app.video_dir = lambda: cls.videos
        cls.before = set(_scratch_dirs())

        cls.stub = appstub.FakeApp(app.MainApp)
        cls.stub.render(2, 7, 3, "ql")

    @classmethod
    def tearDownClass(cls):
        app.video_dir = cls._real_video_dir
        shutil.rmtree(cls.videos, ignore_errors=True)
        for path in set(_scratch_dirs()) - cls.before:
            shutil.rmtree(path, ignore_errors=True)

    def test_it_reported_success(self):
        self.assertEqual(self.stub.failed, [], "".join(self.stub.failed))
        self.assertEqual(len(self.stub.done), 1)

    def test_it_produced_a_video(self):
        video = self.stub.done[0]
        self.assertTrue(os.path.isfile(video))
        self.assertGreater(os.path.getsize(video), 50_000)

    def test_what_it_produced_is_an_mp4(self):
        with open(self.stub.done[0], "rb") as fh:
            head = fh.read(12)
        # ISO base media file format: a box of type 'ftyp' at offset 4.
        self.assertEqual(head[4:8], b"ftyp", head)

    def test_it_left_no_scratch_directory_behind(self):
        self.assertEqual(set(_scratch_dirs()) - self.before, set())

    def test_the_video_is_the_combined_scene_not_a_fragment(self):
        # A single animation of this scene is well under a second; the whole
        # thing is about half a minute. ffprobe is optional, so the size
        # check above is the one that always runs — this one adds the
        # duration when ffprobe happens to be there.
        if shutil.which("ffprobe") is None:
            self.skipTest("ffprobe not on PATH")
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", self.stub.done[0]],
            capture_output=True, text=True,
        )
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertGreater(float(out.stdout.strip()), 20.0)


@unittest.skipUnless(real_manim_present(), "manim is not installed for this python")
class TheSceneAgainstTheRealManim(unittest.TestCase):
    """
    The scene is tested against fakemanim everywhere else. This checks that
    the calls it makes are ones the real library accepts, for the two shapes
    of plan — four steps and the single-step c = 0 case — without waiting for
    a full render.
    """

    def run_dry(self, a, b, c):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        media = tempfile.mkdtemp(prefix="qic_dryrun_")
        cfg = os.path.join(media, "cfg.json")
        with open(cfg, "w", encoding="utf-8") as fh:
            fh.write('{"a": %d, "b": %d, "c": %d}' % (a, b, c))
        env = dict(os.environ, QIC_FACTOR_CONFIG=cfg)
        try:
            return subprocess.run(
                [sys.executable, "-m", "manim", os.path.join(root, "factorize.py"),
                 "FactorizationScene", "-ql", "--dry_run", "--media_dir", media],
                env=env, capture_output=True, text=True,
            )
        finally:
            shutil.rmtree(media, ignore_errors=True)

    def test_a_four_step_plan_plays(self):
        out = self.run_dry(2, 7, 3)
        self.assertEqual(out.returncode, 0, out.stderr[-2000:])

    def test_the_common_factor_plan_plays(self):
        out = self.run_dry(1, 3, 0)
        self.assertEqual(out.returncode, 0, out.stderr[-2000:])

    def test_an_unfactorable_plan_plays(self):
        out = self.run_dry(1, 1, 1)
        self.assertEqual(out.returncode, 0, out.stderr[-2000:])


def _scratch_dirs():
    root = tempfile.gettempdir()
    try:
        names = os.listdir(root)
    except OSError:
        return []
    return [os.path.join(root, n) for n in names if n.startswith("qic_manim_")]


if __name__ == "__main__":
    unittest.main()
