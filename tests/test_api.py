"""
test_api.py — the ctypes boundary with the QIC C library.

Two things are checked here that nothing else can see:

  * the error codes app.py knows about are exactly the ones the C enum
    defines, read out of QIC's own header. The enum grew from four values to
    seven after this frontend was written, and two of the three new ones are
    reachable from ordinary typing — `0x^2+3x+1` and a coefficient too big
    for an int — so the app showed a message that named nothing.

  * the struct this module declares still matches the one the library
    returns. A field added on the C side would otherwise be read as garbage
    coefficients with no error anywhere.

The library itself is a build artefact and is not committed. When it is
missing, the tests that need it report as skipped rather than passing
quietly; build it with `make` in the QIC folder.
"""

import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import app
import qic_api

PARSER_H = os.path.normpath(os.path.join(ROOT, "..", "QIC", "include", "parser.h"))


def read_enum():
    """The ParseError enum from QIC's header, as {value: name}."""
    with open(PARSER_H, encoding="utf-8") as fh:
        text = fh.read()
    body = re.search(r"typedef\s+enum\s*\{(.*?)\}\s*ParseError\s*;", text, re.S)
    if not body:
        raise AssertionError(f"no ParseError enum in {PARSER_H}")
    names = []
    for line in body.group(1).splitlines():
        line = re.sub(r"/\*.*?\*/", "", line).strip().rstrip(",").strip()
        if not line or line.startswith("/*") or line.startswith("*"):
            continue
        assert "=" not in line, f"explicit enum value in {line!r}; update this test"
        names.append(line)
    return dict(enumerate(names))


def read_struct_fields():
    """The QuadraticExpression fields from QIC's header, in order."""
    with open(PARSER_H, encoding="utf-8") as fh:
        text = fh.read()
    body = re.search(
        r"typedef\s+struct\s*\{(.*?)\}\s*QuadraticExpression\s*;", text, re.S)
    if not body:
        raise AssertionError(f"no QuadraticExpression struct in {PARSER_H}")
    fields = []
    for line in body.group(1).splitlines():
        line = re.sub(r"/\*.*?\*/", "", line).strip()
        if not line.endswith(";"):
            continue
        ctype, name = line[:-1].rsplit(None, 1)
        fields.append((ctype.strip(), name.strip()))
    return fields


header_present = os.path.isfile(PARSER_H)


@unittest.skipUnless(header_present, f"QIC header not found at {PARSER_H}")
class TheErrorCodes(unittest.TestCase):

    def test_every_enum_value_has_a_message(self):
        enum = read_enum()
        missing = [
            f"{value} ({name})"
            for value, name in enum.items()
            if value != 0 and value not in app._PARSE_ERRORS
        ]
        self.assertEqual(
            missing, [],
            "the C library can return codes app.py has no message for: "
            + ", ".join(missing),
        )

    def test_no_message_describes_a_code_the_library_cannot_return(self):
        enum = read_enum()
        extra = [code for code in app._PARSE_ERRORS if code not in enum]
        self.assertEqual(extra, [])

    def test_success_is_zero_and_has_no_message(self):
        self.assertEqual(read_enum()[0], "NONE")
        self.assertNotIn(0, app._PARSE_ERRORS)

    def test_the_messages_are_in_the_order_the_header_declares(self):
        enum = read_enum()
        self.assertEqual(enum[4], "NOT_QUADRATIC")
        self.assertEqual(enum[5], "COEFFICIENT_RANGE")
        self.assertEqual(enum[6], "ALLOC_FAILED")


@unittest.skipUnless(header_present, f"QIC header not found at {PARSER_H}")
class TheStructLayout(unittest.TestCase):

    def test_it_has_the_same_fields_in_the_same_order(self):
        declared = [name for _ctype, name in read_struct_fields()]
        mirrored = [name for name, _ctype in qic_api.QuadraticExpression._fields_]
        self.assertEqual(mirrored, declared)

    def test_the_three_coefficients_are_ints(self):
        by_name = dict((n, t) for t, n in read_struct_fields())
        for name in ("a", "b", "c"):
            self.assertEqual(by_name[name], "int")

    def test_the_structure_is_four_ints_wide(self):
        import ctypes

        self.assertEqual(
            ctypes.sizeof(qic_api.QuadraticExpression),
            4 * ctypes.sizeof(ctypes.c_int),
        )


def library_present():
    try:
        qic_api._load()
        return True
    except (FileNotFoundError, OSError):
        return False


@unittest.skipUnless(library_present(), "libqic not built; run make in ../QIC")
class TheRealLibrary(unittest.TestCase):

    def parse(self, text):
        return qic_api.parse(text)

    def test_it_parses_a_plain_quadratic(self):
        r = self.parse("2x^2+7x+3")
        self.assertEqual((r.a, r.b, r.c, r.error), (2, 7, 3, 0))

    def test_it_parses_both_sides_of_an_equation(self):
        r = self.parse("x^2-5x+6=0")
        self.assertEqual((r.a, r.b, r.c, r.error), (1, -5, 6, 0))

    def test_it_parses_a_negative_leading_coefficient(self):
        r = self.parse("-2x^2+4x-2")
        self.assertEqual((r.a, r.b, r.c, r.error), (-2, 4, -2, 0))

    def test_each_error_code_this_app_shows_can_be_produced(self):
        cases = {
            1: "2y^2+1",                      # a character outside the set
            2: "3x+1",                        # no x² term
            3: "2x^2+",                       # malformed
            4: "0x^2+3x+1",                   # parses, but a is 0
            5: "99999999999999x^2+1x+1",      # will not fit in an int
        }
        for code, text in cases.items():
            with self.subTest(text=text):
                self.assertEqual(self.parse(text).error, code)
                self.assertIn(code, app._PARSE_ERRORS)

    def test_a_result_is_usable_by_the_factorizer(self):
        import factorsteps

        r = self.parse("6x^2-x-2")
        self.assertEqual(r.error, 0)
        plan = factorsteps.plan(r.a, r.b, r.c)
        self.assertEqual(plan["final"], "(3x − 2)(2x + 1) = 0")


class TheMissingLibraryMessage(unittest.TestCase):

    def test_it_says_where_to_build_it(self):
        saved = qic_api._lib
        qic_api._lib = None
        real_isfile = qic_api.os.path.isfile
        qic_api.os.path.isfile = lambda _p: False
        try:
            with self.assertRaises(FileNotFoundError) as caught:
                qic_api._load()
        finally:
            qic_api.os.path.isfile = real_isfile
            qic_api._lib = saved

        message = str(caught.exception)
        self.assertIn("make", message)
        self.assertIn("QIC", message)
        # The old message sent people to a "gui/" folder that does not exist.
        self.assertNotIn("gui/", message)


if __name__ == "__main__":
    unittest.main()
