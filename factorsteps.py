"""
factorsteps.py — the factorization itself, with no renderer attached.

`factorize.py` is a Manim scene: importing it pulls in Manim, ffmpeg and a
large native stack, so nothing in it could be exercised without a full render.
Everything that *decides* something now lives here instead — the split, the
grouping, the factors, and every string those produce — and the scene is left
with the animation.

`app.py` uses the same module to print the working as text when Manim is not
installed.

The vocabulary, which matches the method taught with it:

    ax² + bx + c   with   p + q = b   and   p × q = ac
    ax² + px + qx + c
    = gx(a₂x + p₂) + q₂(a₂x + p₂)     g = gcd(a, p), a₂ = a/g, p₂ = p/g, q₂ = q/a₂
    = (gx + q₂)(a₂x + p₂)
"""

from __future__ import annotations

import math
from math import gcd as _gcd

# Generated maths uses U+2212 MINUS SIGN throughout. Python's str() of a
# negative int gives U+002D HYPHEN-MINUS, which is narrower and sits lower;
# mixing the two put both glyphs in the same frame of the video.
MINUS = "−"


# ── Maths ────────────────────────────────────────────────────────────────────

def is_perfect_square(n: int) -> bool:
    if n < 0:
        return False
    r = math.isqrt(n)
    return r * r == n


def discriminant(a: int, b: int, c: int) -> int:
    return b * b - 4 * a * c


def find_split(a: int, b: int, c: int):
    """
    Return (p, q) with p + q = b and p*q = ac, or (None, None) if no such
    pair of integers exists.

    p is the one sharing the larger factor with a, which is what makes the
    grouping step come out in whole numbers.
    """
    d = discriminant(a, b, c)
    if not is_perfect_square(d):
        return None, None
    sd = math.isqrt(d)
    if (b + sd) % 2:
        # Unreachable: d = b² - 4ac means sd² ≡ b² (mod 4), so sd and b always
        # share a parity. Kept because the caller divides by 2 on the next line.
        return None, None
    p1 = (b + sd) // 2
    p2 = (b - sd) // 2
    if _gcd(abs(a), abs(p1)) >= _gcd(abs(a), abs(p2)):
        return p1, p2
    return p2, p1


def factor_params(a: int, p: int, q: int):
    """
    Return (g, a2, p2, q2) such that (g·x + q2)(a2·x + p2) is the factorization.

    Every division here is exact: g divides a and p by construction, and a2
    divides q because p2·q = a2·c with gcd(a2, p2) = 1.
    """
    g = _gcd(abs(a), abs(p))
    a2 = a // g
    p2 = p // g
    q2 = q // a2
    return g, a2, p2, q2


# ── Expression rendering ─────────────────────────────────────────────────────

def coefficient(n: int, first: bool = False, noone: bool = True) -> str:
    m = "" if (noone and abs(n) == 1) else str(abs(n))
    if first:
        return (MINUS + m) if n < 0 else m
    return (f" {MINUS} " + m) if n < 0 else (" + " + m)


def term(coef: int, var: str = "", first: bool = False) -> str:
    """One term of a polynomial, including its sign. Empty when coef is 0."""
    if coef == 0:
        return ""
    noone = bool(var)
    return coefficient(coef, first, noone) + var


def number(n: int) -> str:
    """A bare integer with the typographic minus sign."""
    return str(n).replace("-", MINUS)


def substituted(n: int) -> str:
    """
    A value as it should read when substituted into a formula.

    Negatives are bracketed: without the brackets `b² - 4ac` with b = -5
    prints as `-5²`, which by the usual precedence reads as -(5²) = -25 and
    contradicts the result printed on the same line.
    """
    return f"({MINUS}{abs(n)})" if n < 0 else str(n)


def standard(a: int, b: int, c: int) -> str:
    s = term(a, "x²", first=True)
    s += term(b, "x")
    s += term(c, "")
    return s + " = 0"


def split_form(a: int, p: int, q: int, c: int) -> str:
    s = term(a, "x²", first=True)
    s += term(p, "x")
    s += term(q, "x")
    s += term(c, "")
    return s + " = 0"


def grouped_form(a: int, p: int, q: int, c: int) -> str:
    g1 = term(a, "x²", first=True) + term(p, "x")
    g2 = term(q, "x", first=True) + term(c, "")
    return f"({g1}) + ({g2}) = 0"


def inner_factor(a2: int, p2: int) -> str:
    return term(a2, "x", first=True) + term(p2, "")


def groups_factored_form(g: int, a2: int, p2: int, q2: int) -> str:
    inn = inner_factor(a2, p2)
    gs = "" if g == 1 else str(g)
    qs = "" if abs(q2) == 1 else str(abs(q2))
    op = "+" if q2 >= 0 else MINUS
    return f"{gs}x({inn}) {op} {qs}({inn}) = 0"


def final_form(g: int, a2: int, p2: int, q2: int) -> str:
    fa = term(g, "x", first=True) + term(q2, "")
    return f"({fa})({inner_factor(a2, p2)}) = 0"


def middle_term(b: int) -> str:
    """The middle term as the equation on screen spells it: b = -1 is '−x'."""
    return term(b, "x", first=True)


# ── The plan the scene animates and the fallback prints ──────────────────────

class Step:
    """One labelled transformation: a new equation and a line explaining it."""

    def __init__(self, label: str, equation: str, note: str, final: bool = False):
        self.label = label
        self.equation = equation
        self.note = note
        self.final = final

    def __repr__(self):
        return f"Step({self.label!r}, {self.equation!r})"


def plan(a: int, b: int, c: int) -> dict:
    """
    Work out everything the video shows for ax² + bx + c = 0.

    Raises ValueError when a is 0, which is not a quadratic. The caller
    checks that first — the library reports it as NOT_QUADRATIC — so this is
    a guard rather than a path.
    """
    if a == 0:
        raise ValueError("a must not be zero")

    flipped = a < 0
    if flipped:
        a, b, c = -a, -b, -c

    d = discriminant(a, b, c)
    out = {
        "a": a, "b": b, "c": c,
        "flipped": flipped,
        "equation": standard(a, b, c),
        "discriminant": d,
        "discriminant_line": (
            f"Check: b² {MINUS} 4ac  =  {substituted(b)}² {MINUS} "
            f"4 × {substituted(a)} × {substituted(c)}  =  {number(d)}"
        ),
        "factorable": False,
        "root": None,
        "steps": [],
        "final": None,
    }

    p, q = find_split(a, b, c)
    if p is None:
        out["verdict"] = (
            f"{number(d)} has no whole-number square root,\n"
            "so this equation cannot be factorized using whole numbers."
        )
        return out

    out["factorable"] = True
    out["root"] = math.isqrt(d)
    out["verdict"] = (
        f"√{d} = {out['root']} is a perfect square - so we can factorize!"
    )

    g, a2, p2, q2 = factor_params(a, p, q)
    out["final"] = final_form(g, a2, p2, q2)

    if c == 0:
        # p is b and q is 0 here, so there is nothing to split: every term
        # already contains an x. The four-step route printed an empty bracket
        # for the second group and a "+ 0(...)" term that multiplies out to
        # nothing, so it is not taken.
        out["steps"].append(Step(
            "Step 1 — Extract the Common Factor",
            out["final"],
            "c = 0, so every term already contains x "
            "— there is no middle term to split.",
            final=True,
        ))
        return out

    if b == 0:
        note1 = (
            "There is no middle term, so write it as 0x and split it:  "
            f"{term(p, 'x', first=True)}{term(q, 'x')}"
        )
    else:
        note1 = (
            f"Rewrite '{middle_term(b)}'  as  "
            f"({term(p, 'x', first=True)}{term(q, 'x')})"
        )

    out["steps"] = [
        Step("Step 1 — Split the Middle Term",
             split_form(a, p, q, c), note1),
        Step("Step 2 — Group Terms",
             grouped_form(a, p, q, c),
             "Bracket adjacent pairs of terms."),
        Step("Step 3 — Factor Each Group",
             groups_factored_form(g, a2, p2, q2),
             "Extract the common factor from each group."),
        Step("Step 4 — Extract the Common Factor",
             out["final"],
             "Apply the distributive law in reverse.", final=True),
    ]
    return out


def as_text(a: int, b: int, c: int) -> str:
    """The same working as plain text, for when there is no renderer."""
    pl = plan(a, b, c)
    lines = ["Factorization by Splitting the Middle Term", ""]
    if pl["flipped"]:
        lines.append(
            f"Multiplied through by {MINUS}1 to make the leading coefficient positive."
        )
        lines.append("")
    lines.append(f"    {pl['equation']}")
    lines.append("")
    lines.append(pl["discriminant_line"])
    lines.append(pl["verdict"])
    lines.append("")
    for step in pl["steps"]:
        lines.append(step.label)
        lines.append(f"    {step.equation}")
        lines.append(f"    {step.note}")
        lines.append("")
    if pl["factorable"]:
        lines.append(f"Factorized:  {pl['final']}")
    return "\n".join(lines)
