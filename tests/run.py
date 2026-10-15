"""
run.py — the whole test suite.

    python tests/run.py            # everything
    python tests/run.py steps app  # just those modules

No test framework is installed for this: everything here is `unittest` from
the standard library, so the suite runs against a bare Python with nothing
but the QIC shared library beside it.

Two groups of tests report as skipped rather than failing when what they need
is absent, and the reason is printed at the end so a skip is never silent:

  * test_render.py needs Manim and FFmpeg. Without them the rest of the suite
    still covers the scene, because it plays against tests/fakemanim.py.
  * the parts of test_api.py that call the library need libqic; build it with
    `make` in the QIC folder next to this project.
"""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

MODULES = ["test_original", "test_steps", "test_scene", "test_api",
           "test_app", "test_render"]


def main(argv):
    wanted = argv[1:]
    names = MODULES
    if wanted:
        names = [m for m in MODULES if any(w in m for w in wanted)]
        if not names:
            print(f"no test module matches {wanted}", file=sys.stderr)
            return 2

    loader = unittest.TestLoader()
    suite = unittest.TestSuite(loader.loadTestsFromName(n) for n in names)

    # This project's P1 was scratch directories nobody deleted, so the suite
    # holds itself to the same standard: anything it leaves in the temp
    # folder is reported.
    before = _temp_entries()

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    import baseline
    baseline.cleanup()
    leftover = sorted(_temp_entries() - before)

    if result.skipped:
        print("\nSkipped:")
        for test, reason in result.skipped:
            print(f"  {test.id().split('.')[-1]}: {reason}")

    if leftover:
        print("\nLeft behind in the temp folder:")
        for name in leftover:
            print(f"  {name}")

    print(f"\n{result.testsRun} tests, "
          f"{len(result.failures)} failures, "
          f"{len(result.errors)} errors, "
          f"{len(result.skipped)} skipped, "
          f"{len(leftover)} temp entries left behind")
    return 0 if (result.wasSuccessful() and not leftover) else 1


def _temp_entries():
    """Names in the temp folder that this project could have made."""
    import tempfile

    try:
        names = os.listdir(tempfile.gettempdir())
    except OSError:
        return set()
    return {n for n in names if n.startswith("qic_")}


if __name__ == "__main__":
    sys.exit(main(sys.argv))
