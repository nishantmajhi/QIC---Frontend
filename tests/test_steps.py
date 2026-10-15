"""
test_steps.py — the factorization and every string it produces.

This is the module the video is made of, so the assertions here are about
what a viewer reads: the equations, the notes, and the sign glyphs in them.
"""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import factorsteps as F

MINUS = "−"
HYPHEN = "-"


def equations_of(plan):
    """Every string in a plan that is maths rather than prose."""
    out = [plan["equation"], plan["discriminant_line"]]
    out += [s.equation for s in plan["steps"]]
    if plan["final"]:
        out.append(plan["final"])
    return out


class TheSplit(unittest.TestCase):

    def test_p_and_q_sum_to_b_and_multiply_to_ac(self):
        for a, b, c in [(2, 7, 3), (1, -5, 6), (6, -1, -2), (12, 7, -10),
                        (1, 0, -4), (1, 2, 1), (4, 0, -9)]:
            p, q = F.find_split(a, b, c)
            self.assertIsNotNone(p, (a, b, c))
            self.assertEqual(p + q, b, (a, b, c))
            self.assertEqual(p * q, a * c, (a, b, c))

    def test_no_split_when_the_discriminant_is_not_a_perfect_square(self):
        for a, b, c in [(1, 1, 1), (1, 3, 1), (2, 3, 4)]:
            self.assertEqual(F.find_split(a, b, c), (None, None))

    def test_a_negative_discriminant_is_not_a_perfect_square(self):
        self.assertFalse(F.is_perfect_square(-1))
        self.assertFalse(F.is_perfect_square(-3))
        self.assertTrue(F.is_perfect_square(0))

    def test_p_is_the_one_sharing_the_larger_factor_with_a(self):
        # 6x² - x - 2: the pair is (3, -4), and 3 must come first because
        # gcd(6, 3) = 3 beats gcd(6, -4) = 2. Put the other way round the
        # grouping step needs fractions.
        self.assertEqual(F.find_split(6, -1, -2), (3, -4))


class TheFactorisation(unittest.TestCase):
    """The differential sweep: expand the answer and compare with the input."""

    def test_every_factorable_quadratic_multiplies_back_out(self):
        checked = 0
        for a in range(1, 41):
            for b in range(-60, 61):
                for c in range(-60, 61):
                    if not F.is_perfect_square(F.discriminant(a, b, c)):
                        continue
                    p, q = F.find_split(a, b, c)
                    self.assertIsNotNone(p, (a, b, c))
                    g, a2, p2, q2 = F.factor_params(a, p, q)
                    # Every division must have been exact...
                    self.assertEqual((g * a2, g * p2, a2 * q2), (a, p, q), (a, b, c))
                    # ...and (gx + q2)(a2x + p2) must be the original.
                    self.assertEqual(
                        (g * a2, g * p2 + q2 * a2, q2 * p2), (a, b, c), (a, b, c)
                    )
                    checked += 1
        self.assertGreater(checked, 25000)

    def test_the_root_reported_is_the_square_root_of_the_discriminant(self):
        for a, b, c in [(2, 7, 3), (6, -1, -2), (1, 0, -4)]:
            plan = F.plan(a, b, c)
            self.assertEqual(plan["root"] ** 2, plan["discriminant"])


class TheTermRendering(unittest.TestCase):

    def test_unit_coefficients_lose_their_one_in_front_of_a_variable(self):
        self.assertEqual(F.term(1, "x", first=True), "x")
        self.assertEqual(F.term(-1, "x", first=True), MINUS + "x")
        self.assertEqual(F.term(1, "x"), " + x")
        self.assertEqual(F.term(-1, "x"), f" {MINUS} x")

    def test_unit_constants_keep_their_one(self):
        self.assertEqual(F.term(1, ""), " + 1")
        self.assertEqual(F.term(-1, ""), f" {MINUS} 1")

    def test_a_zero_term_is_nothing_at_all(self):
        self.assertEqual(F.term(0, "x"), "")
        self.assertEqual(F.term(0, ""), "")

    def test_negatives_substituted_into_a_formula_are_bracketed(self):
        # Without the brackets, b = -5 renders as "-5²", which reads as -25.
        self.assertEqual(F.substituted(-5), f"({MINUS}5)")
        self.assertEqual(F.substituted(5), "5")
        self.assertEqual(F.substituted(0), "0")

    def test_the_middle_term_is_spelled_as_the_equation_spells_it(self):
        self.assertEqual(F.middle_term(-1), MINUS + "x")
        self.assertEqual(F.middle_term(1), "x")
        self.assertEqual(F.middle_term(-5), MINUS + "5x")


class TheSignGlyph(unittest.TestCase):
    """One minus sign, everywhere, in everything generated."""

    def test_no_generated_equation_uses_the_ascii_hyphen(self):
        for a in range(-9, 10):
            if a == 0:
                continue
            for b in range(-9, 10):
                for c in range(-9, 10):
                    for text in equations_of(F.plan(a, b, c)):
                        self.assertNotIn(HYPHEN, text, (a, b, c, text))

    def test_the_notes_use_the_same_glyph_as_the_equations(self):
        plan = F.plan(1, -5, 6)
        note = plan["steps"][0].note
        self.assertIn(f"'{MINUS}5x'", note)
        self.assertNotIn(HYPHEN, note)

    def test_a_negative_discriminant_is_printed_with_the_minus_sign(self):
        plan = F.plan(1, 1, 1)
        self.assertIn(f"{MINUS}3", plan["discriminant_line"])
        self.assertTrue(plan["verdict"].startswith(f"{MINUS}3"))


class ThePlan(unittest.TestCase):

    def test_a_typical_quadratic_takes_four_steps(self):
        plan = F.plan(2, 7, 3)
        self.assertTrue(plan["factorable"])
        self.assertEqual(len(plan["steps"]), 4)
        self.assertEqual(
            [s.equation for s in plan["steps"]],
            ["2x² + 6x + x + 3 = 0",
             "(2x² + 6x) + (x + 3) = 0",
             "2x(x + 3) + (x + 3) = 0",
             "(2x + 1)(x + 3) = 0"],
        )
        self.assertTrue(plan["steps"][-1].final)
        self.assertFalse(any(s.final for s in plan["steps"][:-1]))

    def test_an_unfactorable_quadratic_has_no_steps(self):
        plan = F.plan(1, 1, 1)
        self.assertFalse(plan["factorable"])
        self.assertEqual(plan["steps"], [])
        self.assertIsNone(plan["final"])
        self.assertIn("cannot be factorized", plan["verdict"])

    def test_a_negative_leading_coefficient_is_normalized(self):
        flipped = F.plan(-1, 5, -6)
        upright = F.plan(1, -5, 6)
        self.assertTrue(flipped["flipped"])
        self.assertFalse(upright["flipped"])
        self.assertEqual(equations_of(flipped), equations_of(upright))

    def test_a_zero_leading_coefficient_is_refused(self):
        with self.assertRaises(ValueError):
            F.plan(0, 3, 1)


class TheConstantlessCase(unittest.TestCase):
    """c = 0: x is a common factor and there is no middle term to split."""

    def test_it_does_not_pretend_to_split_anything(self):
        plan = F.plan(1, 3, 0)
        self.assertEqual(len(plan["steps"]), 1)
        self.assertIn("Common Factor", plan["steps"][0].label)
        self.assertNotIn("Split", plan["steps"][0].label)

    def test_it_draws_no_empty_bracket_and_no_zero_term(self):
        for b in range(-6, 7):
            for a in (1, 2, 3, 6):
                plan = F.plan(a, b, 0)
                for text in equations_of(plan):
                    self.assertNotIn("()", text, (a, b))
                    self.assertNotIn("0(", text, (a, b))

    def test_the_answer_is_still_the_fully_factored_one(self):
        self.assertEqual(F.plan(3, 6, 0)["final"], "(3x)(x + 2) = 0")
        self.assertEqual(F.plan(1, 3, 0)["final"], "(x)(x + 3) = 0")

    def test_the_note_says_why_there_is_no_split(self):
        self.assertIn("c = 0", F.plan(1, 3, 0)["steps"][0].note)


class TheMiddleTermlessCase(unittest.TestCase):
    """b = 0: the split is real, but the term being split is not on screen."""

    def test_the_note_does_not_quote_a_term_the_equation_never_showed(self):
        plan = F.plan(1, 0, -4)
        self.assertNotIn("0x", plan["equation"])
        note = plan["steps"][0].note
        self.assertNotIn("'0x'", note)
        self.assertIn("no middle term", note)
        self.assertIn(f"2x {MINUS} 2x", note)

    def test_the_four_steps_are_still_taken(self):
        plan = F.plan(1, 0, -4)
        self.assertEqual(len(plan["steps"]), 4)
        self.assertEqual(plan["final"], f"(x {MINUS} 2)(x + 2) = 0")


class TheTextFallback(unittest.TestCase):

    def test_it_contains_the_equation_the_steps_and_the_answer(self):
        text = F.as_text(2, 7, 3)
        self.assertIn("2x² + 7x + 3 = 0", text)
        for step in F.plan(2, 7, 3)["steps"]:
            self.assertIn(step.equation, text)
            self.assertIn(step.note, text)
        self.assertIn("Factorized:  (2x + 1)(x + 3) = 0", text)

    def test_it_says_so_when_nothing_can_be_factorized(self):
        text = F.as_text(1, 1, 1)
        self.assertIn("cannot be factorized", text)
        self.assertNotIn("Factorized:", text)

    def test_it_reports_a_normalized_sign(self):
        self.assertIn("Multiplied through by", F.as_text(-1, 5, -6))
        self.assertNotIn("Multiplied through by", F.as_text(1, -5, 6))


if __name__ == "__main__":
    unittest.main()
