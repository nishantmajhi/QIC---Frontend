"""
test_scene.py — what the video actually shows.

The scene is played against fakemanim, which records the text of every
mobject handed to `self.play` instead of rendering it, so these assertions
are made against the strings that reach the screen. Two of the defects fixed
in this pass were in code whose numbers were right and whose screen was
wrong, which is why the readback is worth the harness.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import fakemanim

fakemanim.install()

import factorsteps as F   # noqa: E402  (after install(), like factorize.py)
import factorize          # noqa: E402
import scenerun           # noqa: E402

MINUS = "−"
HYPHEN = "-"


def lines(a, b, c):
    return scenerun.lines(factorize, a, b, c)


def equation_sequence(a, b, c):
    """
    The equations the viewer sees, in order, one entry per change.

    A ReplacementTransform is recorded with both its source and its target,
    so every equation shows up twice in the raw list — once as the thing that
    is replaced next. Consecutive repeats are collapsed here; a repeat that
    survives means the screen genuinely did not change.
    """
    out = []
    for drawn in lines(a, b, c):
        if not drawn.endswith("= 0"):
            continue
        if out and out[-1] == drawn:
            continue
        out.append(drawn)
    return out


class TheOrderOfTheVideo(unittest.TestCase):

    def test_it_runs_title_equation_check_then_four_steps(self):
        shown = lines(2, 7, 3)
        self.assertEqual(shown[0], "Factorization by Splitting the Middle Term")
        self.assertEqual(shown[1], "2x² + 7x + 3 = 0")
        self.assertTrue(shown[2].startswith("Check: b²"))
        self.assertIn("perfect square", shown[3])
        for label in ("Step 1 — Split the Middle Term",
                      "Step 2 — Group Terms",
                      "Step 3 — Factor Each Group",
                      "Step 4 — Extract the Common Factor"):
            self.assertIn(label, shown)
        self.assertEqual(shown[-1], "✓   Factorization Complete")

    def test_the_last_equation_drawn_is_the_answer(self):
        for a, b, c in [(6, -1, -2), (2, 7, 3), (1, 3, 0), (1, 0, -4)]:
            self.assertEqual(equation_sequence(a, b, c)[-1],
                             F.plan(a, b, c)["final"], (a, b, c))

    def test_it_stops_after_the_check_when_nothing_factorizes(self):
        shown = lines(1, 1, 1)
        self.assertNotIn("Factorization Complete", " ".join(shown))
        self.assertTrue(any("cannot be factorized" in s for s in shown))
        self.assertFalse(any(s.startswith("Step ") for s in shown))

    def test_the_flip_note_appears_only_for_a_negative_leading_coefficient(self):
        self.assertTrue(any("multiplied by" in s for s in lines(-1, 5, -6)))
        self.assertFalse(any("multiplied by" in s for s in lines(1, -5, 6)))


class TheSceneInventsNothing(unittest.TestCase):
    """Every string drawn comes from the plan, so the tests above cover both."""

    def test_every_equation_and_note_drawn_is_in_the_plan(self):
        for a, b, c in [(2, 7, 3), (1, -5, 6), (1, 0, -4), (1, 3, 0),
                        (1, 1, 1), (-1, 5, -6), (12, 7, -10)]:
            plan = F.plan(a, b, c)
            allowed = {
                "Factorization by Splitting the Middle Term",
                "✓   Factorization Complete",
                "Equation multiplied by −1 to normalize the leading coefficient.",
                plan["equation"], plan["discriminant_line"], plan["verdict"],
            }
            for step in plan["steps"]:
                allowed.update({step.label, step.equation, step.note})
            for drawn in lines(a, b, c):
                self.assertIn(drawn, allowed, (a, b, c))


class TheDegenerateCases(unittest.TestCase):

    def test_no_empty_bracket_is_ever_drawn(self):
        for b in range(-6, 7):
            for a in (1, 2, 3):
                for drawn in lines(a, b, 0):
                    self.assertNotIn("()", drawn, (a, b))

    def test_no_term_multiplied_by_zero_is_ever_drawn(self):
        for b in range(-6, 7):
            for drawn in lines(1, b, 0):
                self.assertNotIn(" 0(", drawn, b)

    def test_every_step_changes_the_equation_on_screen(self):
        for a, b, c in [(2, 7, 3), (1, -5, 6), (1, 0, -4), (1, 3, 0), (3, 6, 0),
                        (1, 0, 0), (12, 7, -10)]:
            plan = F.plan(a, b, c)
            expected = [plan["equation"]] + [s.equation for s in plan["steps"]]
            # Collapsing consecutive repeats cannot shorten this list: a step
            # that leaves the equation alone would drop out of it.
            self.assertEqual(equation_sequence(a, b, c), expected, (a, b, c))


class TheSignGlyphOnScreen(unittest.TestCase):

    def test_one_frame_never_contains_both_minus_glyphs(self):
        for a, b, c in [(1, -5, 6), (1, 0, -4), (6, -1, -2), (12, 7, -10),
                        (1, -2, 1), (-1, 5, -6)]:
            for drawn in lines(a, b, c):
                if HYPHEN in drawn:
                    # Prose may hyphenate ("whole-number"); maths may not.
                    self.assertNotIn(MINUS, drawn, (a, b, c, drawn))

    def test_the_discriminant_line_brackets_its_negatives(self):
        disc = [s for s in lines(1, -5, 6) if s.startswith("Check:")][0]
        self.assertIn(f"({MINUS}5)²", disc)
        self.assertNotIn("-5", disc)


class TheConfigFile(unittest.TestCase):

    def test_it_is_read_from_the_environment_variable(self):
        # scenerun sets QIC_FACTOR_CONFIG; if the scene ignored it, every
        # case above would render the same equation.
        self.assertIn("2x² + 7x + 3 = 0", lines(2, 7, 3))
        self.assertIn("x² + 3x = 0", lines(1, 3, 0))


if __name__ == "__main__":
    unittest.main()
