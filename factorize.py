"""
factorize.py — Manim scene: quadratic factorization by splitting the middle term.

Config is read from the JSON file pointed to by the QIC_FACTOR_CONFIG env var.
JSON format: {"a": 2, "b": 7, "c": 3}

Run standalone (for testing):
    QIC_FACTOR_CONFIG=qic_config.json python -m manim factorize.py FactorizationScene -ql

The maths and every string it produces live in `factorsteps.py`, which imports
nothing. This file is the animation: what moves, in what colour, for how long.

NOTE: Uses Manim's Text/Pango renderer throughout (no LaTeX / dvisvgm required).
"""

from __future__ import annotations

from manim import *
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import factorsteps


# ── Config ────────────────────────────────────────────────────────────────────

def _load_cfg() -> dict:
    path = os.environ.get("QIC_FACTOR_CONFIG", "qic_config.json")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


# ── Scene ─────────────────────────────────────────────────────────────────────

_TITLE_Y = 3.3
_EQ_Y    = 0.8
_NOTE_Y  = -1.0
_STEP_Y  = 2.0

# VS Code-inspired palette
_CL = dict(
    title  = "#D4D4D4",   # VS Code primary text
    eq     = "#DCDCAA",   # VS Code yellow (variables/functions)
    label  = "#9CDCFE",   # VS Code light-blue (parameters)
    note   = "#6A9955",   # VS Code green (comments)
    ok     = "#4EC9B0",   # VS Code teal (types)
    bad    = "#F44747",   # VS Code red (errors)
    factor = "#4FC1FF",   # VS Code bright cyan
    dim    = "#808080",   # VS Code comments / dimmed
)

_MATH_FONT = "DejaVu Sans"


class FactorizationScene(Scene):

    # ── Scene background ──────────────────────────────────────────────────────
    def setup(self):
        self.camera.background_color = "#1E1E1E"   # VS Code editor background

    def construct(self):
        cfg = _load_cfg()
        plan = factorsteps.plan(cfg["a"], cfg["b"], cfg["c"])

        self._eq_mob = None

        self._show_title(plan["flipped"])
        self._show_equation(plan["equation"])
        self._check_discriminant(plan)

        if not plan["factorable"]:
            return

        for step in plan["steps"]:
            if step.final:
                self._final_step(step)
            else:
                self._replace_eq(step.equation, step.label, self._mk_note(step.note))

    # ── Mobject factories ─────────────────────────────────────────────────────

    def _mk_eq(self, text: str, color=None) -> Text:
        m = Text(text, font=_MATH_FONT, font_size=44, color=color or _CL["eq"])
        m.move_to(UP * _EQ_Y)
        return m

    def _mk_label(self, text: str) -> Text:
        t = Text(text, font_size=26, color=_CL["label"])
        t.move_to(UP * _STEP_Y)
        return t

    def _mk_note(self, text: str) -> Text:
        t = Text(text, font=_MATH_FONT, font_size=24, color=_CL["note"])
        t.move_to(UP * _NOTE_Y)
        return t

    # ── Transition helper ─────────────────────────────────────────────────────

    def _replace_eq(self, new_text: str, label: str,
                    note: Mobject | None = None,
                    color=None, rt: float = 1.1):
        lbl    = self._mk_label(label)
        new_eq = self._mk_eq(new_text, color)
        anims  = [Write(lbl), ReplacementTransform(self._eq_mob, new_eq)]
        if note:
            anims.append(FadeIn(note, shift=UP * 0.15))
        self.play(*anims, run_time=rt)
        self._eq_mob = new_eq
        self.wait(1.4)
        fade = [FadeOut(lbl)]
        if note:
            fade.append(FadeOut(note))
        self.play(*fade, run_time=0.4)
        self.wait(0.25)

    # ── Sections ──────────────────────────────────────────────────────────────

    def _show_title(self, flipped: bool):
        t = Text(
            "Factorization by Splitting the Middle Term",
            font_size=32, color=_CL["title"],
        )
        t.move_to(UP * _TITLE_Y)
        ul = Underline(t, color=_CL["title"], buff=0.05)
        self.play(Write(t), Write(ul), run_time=0.9)
        if flipped:
            note = Text(
                "Equation multiplied by −1 to normalize the leading coefficient.",
                font_size=18, color=_CL["dim"],
            )
            note.next_to(t, DOWN, buff=0.15)
            self.play(FadeIn(note))
        self.wait(0.5)

    def _show_equation(self, equation: str):
        eq = self._mk_eq(equation)
        self.play(Write(eq), run_time=1.1)
        self._eq_mob = eq
        self.wait(0.9)

    def _check_discriminant(self, plan: dict):
        # Show the discriminant formula with numbers plugged in
        disc = Text(
            plan["discriminant_line"],
            font=_MATH_FONT, font_size=30, color=_CL["note"],
        )
        disc.move_to(UP * _NOTE_Y)
        self.play(Write(disc), run_time=0.9)
        self.wait(0.7)

        if not plan["factorable"]:
            fail = Text(
                plan["verdict"],
                font_size=26, color=_CL["bad"],
                line_spacing=1.6,
            )
            fail.next_to(disc, DOWN, buff=0.45)
            self.play(FadeIn(fail))
            self.wait(4)
            return

        chk = Text(
            plan["verdict"],
            font=_MATH_FONT, font_size=28, color=_CL["ok"],
        )
        chk.next_to(disc, DOWN, buff=0.32)
        self.play(Write(chk), run_time=0.8)
        self.wait(1.2)
        self.play(FadeOut(VGroup(disc, chk)))
        self.wait(0.3)

    def _final_step(self, step):
        note   = self._mk_note(step.note)
        lbl    = self._mk_label(step.label)
        new_eq = self._mk_eq(step.equation, color=_CL["factor"])

        self.play(
            Write(lbl),
            ReplacementTransform(self._eq_mob, new_eq),
            FadeIn(note, shift=UP * 0.15),
            run_time=1.1,
        )
        self._eq_mob = new_eq
        self.wait(1.4)
        self.play(FadeOut(lbl), FadeOut(note))

        done = Text("✓   Factorization Complete", font_size=36, color=_CL["ok"])
        done.move_to(DOWN * 1.8)
        self.play(Write(done))
        self.wait(3)
