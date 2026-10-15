"""
qic_api.py — ctypes wrapper for libqic shared library.

Search order for the library:
  1. Same directory as this file          (QIC - Frontend/libqic.dll|so)
  2. Parent directory                     (../libqic.dll|so)
  3. Sibling QIC build directory          (../QIC/libqic.dll|so)

The library is a build artefact and is not committed to the QIC repository,
so a fresh clone has to run `make` there before this module can load it. The
error raised when it is missing says so.
"""

import ctypes
import os
import platform


# ── Structs ─────────────────────────────────────────────────────────────────

class QuadraticExpression(ctypes.Structure):
    """
    Mirrors `QuadraticExpression` in QIC's include/parser.h, field for field.

    If the GUI starts reporting coefficients that make no sense, a change to
    that struct is the first thing to check.
    """

    _fields_ = [
        ("a",     ctypes.c_int),
        ("b",     ctypes.c_int),
        ("c",     ctypes.c_int),
        # ParseError, an enum, which the C compilers this is built with give
        # int width: 0=NONE 1=INVALID_INPUT 2=INVALID_DEGREE
        # 3=INVALID_EQUATION 4=NOT_QUADRATIC 5=COEFFICIENT_RANGE
        # 6=ALLOC_FAILED. app.py maps these to messages by value.
        ("error", ctypes.c_int),
    ]

    def __repr__(self):
        return (f"QuadraticExpression(a={self.a}, b={self.b}, c={self.c}, "
                f"error={self.error})")


# ── Library loading ──────────────────────────────────────────────────────────

_lib = None

def _load() -> ctypes.CDLL:
    global _lib
    if _lib is not None:
        return _lib

    lib_name = "libqic.dll" if platform.system() == "Windows" else "libqic.so"
    here = os.path.dirname(os.path.abspath(__file__))

    candidates = [
        os.path.join(here, lib_name),                    # gui/
        os.path.join(here, "..", lib_name),              # ../
        os.path.join(here, "..", "QIC", lib_name),       # ../QIC/
    ]

    for path in candidates:
        path = os.path.normpath(path)
        if os.path.isfile(path):
            _lib = ctypes.CDLL(path)
            _lib.qic_parse.restype  = QuadraticExpression
            _lib.qic_parse.argtypes = [ctypes.c_char_p]
            return _lib

    raise FileNotFoundError(
        f"Cannot find '{lib_name}'.\n"
        f"Build it by running 'make' (or 'mingw32-make') in the QIC folder "
        f"next to this one. Building leaves '{lib_name}' in QIC/, where this "
        f"app looks for it; no copying is needed."
    )


# ── Public API ───────────────────────────────────────────────────────────────

def parse(equation: str) -> QuadraticExpression:
    """
    Parse a raw equation string using the QIC C library.
    Normalization (whitespace stripping, case folding) is done inside the library.

    Returns a QuadraticExpression.  Check .error before using .a / .b / .c:
        0  NONE              — success
        1  INVALID_INPUT     — unsupported characters
        2  INVALID_DEGREE    — no x² term, or an exponent that is not 2
        3  INVALID_EQUATION  — malformed structure
        4  NOT_QUADRATIC     — parsed cleanly, but a is 0
        5  COEFFICIENT_RANGE — a coefficient does not fit in an int
        6  ALLOC_FAILED      — the library ran out of memory
    """
    return _load().qic_parse(equation.encode("utf-8"))
