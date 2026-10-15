# Code Review — QIC Frontend

First pass 2026-09-04. **Remediated 2026-09-24**; this file is now a record of
what was fixed, what was deliberately left alone, and what is worth knowing
next time.

The original review is kept below, under "The first review", with each of its
findings marked up. Read the corrections first.

---

## Corrections to the first review

**The project was listed as possibly unrunnable on this machine. It runs.**
Every handover note since 2026-09-21 said Manim was not installed and that
getting it would be "a plausible hour" with a Cairo/Pango stack to build.
`pip install manim==0.18.1` into a virtualenv took four minutes and needed no
native toolchain at all — pycairo and manimpango both ship Windows wheels —
and **FFmpeg was already on `PATH`** at
`C:\ProgramData\chocolatey\bin\ffmpeg.exe`. The very first real render
produced a 32-second 480p video of `2x² + 7x + 3`. That is the same lesson
`C++/OpenGL/UnlimitedTetris` taught on 2026-09-21: check whether the machine
already has the dependency before writing the project off.

**Finding 5 was right, and understated.** The review said a fourth error code
would make the dictionary "silently return `None`". By the time it was read,
QIC's own pass had already added **three** — the enum now has seven values —
and two of the new ones are reachable by typing:

```
0x^2+3x+1                →  4  NOT_QUADRATIC
99999999999999x^2+1x+1   →  5  COEFFICIENT_RANGE
```

Both produced "Parse error — check the equation and retry.", which names
nothing. This was the ten-minute follow-up `CONTINUE-HERE.md` recorded from
QIC's pass, and it was real.

**Finding 6 was right about the cause but wrong about the consequence.** It
said a render "cannot be stopped except by closing the app — which leaves the
Manim process running", and treated that as an argument for a Cancel button.
The leaked process is the more serious half and does not need a button: the
renderer is now started with `Popen`, held on to, and terminated when the
window closes. Measured with the real thing — two renderer processes running
mid-flight, zero two seconds after the close.

**The smaller note about `_open_file` was correct as written.** It asked
whether the Windows branch used `os.startfile` rather than `start`. It does.
Nothing needed changing there for the reason given, although the call itself
turned out to need a guard for a different one (see New finding 2).

---

## What was fixed

### The P1: a media directory per render, kept for ever

`_render` created `tempfile.mkdtemp(prefix="qic_manim_")` and the `finally`
block cleaned up only the JSON config. Quantified on this machine with a real
render: **46 files and 1.2 MB for one 480p video**, of which the video is one
file and 423 KB. The rest is a fragment per animation — 27 of them — plus
Manim's caches. At `-qh` it is several times that.

The video is the deliverable, so it is copied into one directory the app owns
(`<temp>/qic-frontend-videos/`) and the scratch directory is deleted in the
`finally`, on every path including failure. Videos are *not* deleted when the
app exits — the one just opened is probably still in a player, and on Windows
the player holds the file — so they are swept at startup once they are a day
old. `tests/test_app.py` covers the success path, the failure path, the
throwing path, and the sweep.

### Parse-error messages that name the error (finding 5)

All seven enum values are in the table now. Rather than the review's
suggestion of a `qic_error_string()` on the C side — which would mean editing
a different project — `tests/test_api.py` **reads `../QIC/include/parser.h`**,
parses the enum out of it, and fails if a value there has no message here or
the other way round. The header already carries a comment saying the values
are appended and never reordered because this frontend maps them by number;
the test is what makes that comment true rather than hopeful.

### The renderer is optional now (finding 4)

`app.py` asks `importlib.util.find_spec("manim")` before it shells out, and
when the answer is no it shows the whole factorization as text — the same
equations and the same notes the video would have shown, from the same
function — with the install command. Previously it ran `python -m manim`
anyway and put `ModuleNotFoundError` in a scrollable box.

### The pin, the licence and the ignore file (findings 3, and the smaller notes)

`manim>=0.18,<0.19`, with a comment saying what was tested and why the top is
closed. MIT `LICENSE` matching the sibling project. A `.gitignore` covering
`__pycache__/`, the shared library and Manim's output.

### The structure

`factorsteps.py` is new and is the point of the rest. It holds the split, the
grouping, the factors and every string those produce, and imports nothing but
`math`. `factorize.py` is now the animation alone — what moves, in what
colour, for how long — and `app.py` uses the same module for the text
fallback, so the two outputs cannot disagree.

That is what made the video testable. `tests/fakemanim.py` stands in for the
whole `manim` package and records the text of everything a scene draws
instead of drawing it, so a test reads back what reached the screen. The
suite runs in three seconds with no Manim installed.

---

## New findings the first review did not make

Ten, of which six are about what the video says. The first review read the
code carefully and correctly; it never watched a frame.

**1. An exception in the render thread locked the window for ever.** `_render`
ran on a daemon thread with no `try`. Anything raised before the
`self._root.after(...)` call — `Popen` failing to start, a disk error writing
the config — ended the thread silently with the button disabled, the entry
disabled and the progress bar still pulsing. The only way out was to close the
app. Reproduced against the original in
`tests/test_original.py::TheLockedWindow`. Every path now reports through
`_on_fail`, which unlocks.

**2. A video that could not be opened failed silently.** `_on_done` set the
status to "opening video" and called `os.startfile`, which raises when
nothing is associated with `.mp4`. That runs inside a Tk callback, where the
traceback goes to a console a windowed app does not have: the user read
"Render complete — opening video" and watched nothing open. It now says where
the file is.

**3. The mp4 search could hand back a one-animation fragment.** `os.walk` for
the first `.mp4` happened to find the combined file because it sits in a
shallower directory, but if the combine step had failed the walk would have
found `partial_movie_files/` instead and opened a one-second clip as the
render. Fragments are excluded by name now, and a media directory with only
fragments in it reports "no video file was produced".

**4. Closing the app left the renderer running.** See the correction to
finding 6 above.

**5. Closing the window raised out of a Tk callback.** `<Configure>` keeps
arriving while widgets are being destroyed, and `_on_resize` reconfigured an
entry that no longer existed:
`TclError: invalid command name ".!frame.!frame.!entry"`. Found by running the
app for real, not by any test.

**6. `c = 0` drew an empty bracket.** `x² + 3x = 0` produced, in order:

```
Step 1 — Split the Middle Term     x² + 3x = 0        (unchanged)
Step 2 — Group Terms               (x² + 3x) + () = 0
Step 3 — Factor Each Group         x(x + 3) + 0(x + 3) = 0
```

with a note offering to "Rewrite '3x' as (3x + 0x)". The answer at the end was
right; the three steps to it were a claim to have split a term that was never
split, an equation with an empty group in it, and a term that multiplies out
to nothing. When `c = 0` the method does not apply — `x` is already a common
factor — so the video now takes it out in one step and says why.

**7. `b = 0` quoted a term that was never on screen.** `x² − 4 = 0` showed the
note "Rewrite '0x' as (2x − 2x)" beside an equation with no `0x` in it. The
split itself is real and correct here; only the wording was wrong, and it now
says there is no middle term and that it is being written as `0x` first.

**8. The discriminant line printed `-5²`.** For `x² − 5x + 6`:

```
Check: b² − 4ac  =  -5² − 4 × 1 × 6  =  1
```

`-5²` reads as −(5²) = −25 by the usual precedence, on the same line as the 1
it is supposed to produce. Negatives substituted into a formula are bracketed
now: `(−5)²`.

**9. Two different minus signs in the same frame.** The expression builders
used U+2212 MINUS SIGN, but every value interpolated with an f-string came
out of `str(int)` with U+002D HYPHEN-MINUS, so `(x² − 2x) + (-3x + 6) = 0`
contained both glyphs at different widths and heights. All generated maths
uses U+2212 now, and a test sweeps every equation of every plan for
a ≠ 0 in −9..9 to keep it that way.

**10. The split note spelled unit coefficients with a 1.** `x² − 2x + 1` drew
`x² − x − x + 1` and captioned it "Rewrite '-2x' as (-1x − 1x)". The note is
built from the same term renderer as the equation now.

---

## Verified and correct

Worth recording, because it is where the search did *not* find anything:

- **The factorization itself.** 27,439 cases — every `a` in 1..40, `b` and `c`
  in −60..60 whose discriminant is a perfect square — checked that
  `p + q = b`, `p·q = ac`, that all three divisions in `factor_params` are
  exact, and that `(gx + q₂)(a₂x + p₂)` multiplies back out to the input. No
  failures. The maths in this project was right; its presentation was not.
- **The subprocess handling.** Argument lists throughout, no shell, and the
  coefficients passed through a temp file named by an environment variable
  rather than on the command line. The first review praised this and was
  right to.
- **The `root.after` marshalling.** Every UI update from the worker goes
  through it. It is now wrapped in `_post`, which drops the callback if the
  window has gone, but the design is the original's.
- **The three-path library search**, and its error message, which was the one
  place the original told the user exactly what to do. The message now names
  the right folder: it said "the gui/ folder", which this project has not
  been called for some time.

---

## Deliberately not done

- **A Cancel button.** The review's finding 6 asked for one. That is a change
  to the interface, which the standing constraint puts out of scope, and the
  part of it with a real consequence — the abandoned process — is fixed
  without one.
- **Moving the duplicated colour theme out of `app.py`.** Two dictionaries in
  one file. It is presentation, and it is fine where it is.
- **The status line's `2x² +7x +3 = 0`.** `{b:+}` gives "+7x" rather than
  "+ 7x". It is the window's own copy rather than generated maths, so it was
  left alone; the video and the text fallback both space it properly.
- **Anything in `../QIC`.** The error codes are mapped on this side and
  checked against that side's header by a test. No file in the C project was
  touched.

### One judgement call worth flagging

Fixing finding 6 above changes **what the video shows** for `c = 0`: one step
where there used to be four. That is closer to the UI line than anything else
in this pass. The reasoning for crossing it is that the four steps were not a
design anyone chose — they were the general case running with `q = 0`
substituted into it, producing an empty bracket and a term worth nothing, and
a claim to have performed a split that had not happened. The answer was never
wrong; the working shown to get there was. Nothing about the layout, the
colours, the timing or the interaction changed.

---

## Notes for a future session

- **Manim is installed now**, at `D:\dev-tools\venvs\qic\` (0.18.1, Python
  3.12). FFmpeg is on `PATH` already. Run the suite with that interpreter to
  include the real render; any other Python skips those eight tests and says
  so.
- **`tests/fakemanim.py` is reusable.** It is 200 lines and it makes a Manim
  scene testable with no Manim: install it in `sys.modules` and the scene
  records the text of what it draws. Anything else in this archive that
  animates would want the same shape. Note that it shadows the real `manim`
  for the rest of the process, which is why the two tests that ask whether
  Manim is really installed ask a subprocess instead.
- **The riskiest coupling is still `qic_api.QuadraticExpression`.** It must
  match `parser.h` field for field. There is a test for that now — it reads
  the header — but it can only check the names, the order and the width. If
  the GUI ever reports nonsense coefficients, look there first.
- **The suite checks that it leaves nothing in the temp folder**, because
  that is what this project's P1 was. `tests/run.py` prints anything it finds
  and fails the run.

---

# The first review

Reviewed 2026-09-04 against the working tree. Scope: `app.py`, `qic_api.py`,
`factorize.py`, `requirements.txt`, `README.md`. Kept verbatim; the markers
in brackets were added on 2026-09-24.

## What this project is

A Tkinter desktop front end for the QIC C library. It loads `libqic.so` / `libqic.dll` through
ctypes to parse and solve a quadratic, then shells out to Manim to render an animated factorisation
video of the result.

## Verdict

The integration work is done carefully. Subprocess calls use argument lists rather than shell
strings, so there is no injection surface even though user input reaches the renderer. Configuration
is handed to the Manim scene through an environment variable pointing at a temp JSON file rather than
through the command line. The render runs on a daemon thread and every UI update comes back through
`root.after`, which is the correct way to touch Tkinter from a worker. The library loader tries three
sensible paths and, when it fails, tells the user exactly how to build the missing file.

Two real defects: temp directories are never cleaned up, and the project depends on binaries that
should not exist in the repository it loads them from.

## Findings

**1. Every render leaks a temp directory.** [**FIXED** — and measured: 46 files, 1.2 MB per 480p
render.] `_render` creates `media_dir` with
`tempfile.mkdtemp(prefix="qic_manim_")` at `app.py:510`, and the `finally` block cleans up only
`cfg_path`. The Manim output directory — containing the rendered MP4, partial movie files, and
Manim's cache — stays behind forever. Render twenty equations and you have twenty directories of
video in your temp folder.

The fix needs a little care because the MP4 is the deliverable: copy the finished file somewhere the
UI owns, then `shutil.rmtree(media_dir)` in the `finally`. Track the directories in a list and clean
them on application exit as a backstop.

**2. The library search depends on committed binaries.** [**RESOLVED ELSEWHERE, DOCUMENTED HERE** —
QIC's own pass untracked them on 2026-09-19. The README now has the build step.] `_load()` looks for
the shared library in
the frontend directory, its parent, and `../QIC/`. That last path works today only because
`libqic.dll` and `libqic.so` are committed to the QIC repository — which they should not be (see that
project's review). Once they are untracked, this frontend stops working on a fresh clone with the
error message pointing at `make`.

That message is good, but it should also appear in this project's README, which currently assumes the
library is simply present. Add a "Build the library first" step with the exact commands for Windows
and Linux.

**3. `manim>=0.18.0` is the entire `requirements.txt`, unpinned.** [**FIXED** — `>=0.18,<0.19`, and
the README lists tkinter, FFmpeg and the library.] Manim's scene API changes between
minor versions, and `factorize.py` is 314 lines written against a specific one. An open-ended lower
bound means a fresh install six months from now pulls a version whose API has moved and the render
fails with a traceback the user cannot interpret. Pin a tested version, or at minimum an upper bound.
`tkinter` and the ctypes dependency on the C library are documented only in the module docstring —
put them in the README too.

**4. Manim is a heavyweight dependency for a quadratic solver.** [**FIXED** — the text fallback.]
It pulls in ffmpeg, Cairo, Pango and
a large Python stack, and a render takes seconds to minutes. That is a fine trade for the visual
payoff, but the app should degrade gracefully: if `-m manim` is not importable, show the algebraic
factorisation as text rather than an error. Right now the animation is the only output path.

**5. Parse error messages are a hardcoded dictionary keyed by integer.** [**FIXED, and it was
understated** — the enum had already grown by three. See the corrections above.]
`_PARSE_ERRORS` at
`app.py:32-36` maps `1`, `2`, `3` to strings that mirror the C enum in `qic.h`. Nothing keeps them in
sync — add a fourth error code on the C side and this dictionary silently returns `None` for it. Have
the C library expose a `qic_error_string()` function and call that, or at minimum add a comment on
both sides pointing at the other.

**6. Renders cannot be cancelled.** [**HALF FIXED, DELIBERATELY** — no Cancel button, but the
renderer is terminated when the window closes.] The thread is a daemon and the subprocess handle is
local to
`_render`, so a high-quality render that takes two minutes cannot be stopped except by closing the
app — which leaves the Manim process running. Keep a reference to the `Popen` object and add a Cancel
button that terminates it.

## Smaller notes

- `subprocess.Popen(["open", path])` and `["xdg-open", path]` at `:591-593` open the finished video.
  There is presumably a Windows branch above them; confirm it uses `os.startfile` rather than
  `start`, which needs a shell. [**CHECKED** — it does, and always did.]
- The VS Code-derived colour theme is duplicated as two dictionaries in `app.py`. Fine for one file,
  but if the app grows, move it out. [**LEFT** — presentation.]
- No tests, no `LICENSE`, no `.gitignore` (so `__pycache__/` is one `git add -A` away).
  [**FIXED** — 108 tests, MIT, and an ignore file.]

## Cleanup

No debug prints, no secrets, no analytics, no dead code. The module docstring accurately lists what
must be installed, which is more than most scripts do. [**CONFIRMED** — nothing of the sort was found
in this pass either.]

## Action checklist

- [x] **P1** Clean up `media_dir` after each render; add an exit-time sweep.
- [x] **P2** Pin the Manim version; document the build-the-library-first step in the README.
- [x] **P2** Derive parse-error strings from the C library instead of a parallel dictionary.
      *(Done as a test that reads the header, rather than by editing the C project.)*
- [x] **P3** Fall back to a text factorisation when Manim is unavailable.
- [~] **P3** Make renders cancellable; add `.gitignore` and `LICENSE`.
      *(Ignore file and licence added. No Cancel button — see "Deliberately not done".)*

## Notes for a future session

Run with `python app.py` after building the QIC library and putting it next to the script (or in
`../QIC/`). The riskiest coupling is `qic_api.py`'s ctypes declaration of the `QuadraticExpression`
struct — it must match the layout in `qic.h` field for field. If the GUI starts reporting nonsense
coefficients after a change to the C side, that mismatch is the first thing to check. [**Still true,
and there is a test for it now.**]

## Licence, 2026-10-02

The author chose one licence for all of their projects: free for personal,
non-commercial use, modifiable for the user's own use, and not to be
distributed, original or modified. No standard licence says that, so `LICENSE`
is a short custom text, the same in every project apart from the year and what
it excludes. The README's licence section says the same. Anything above that
calls the licence an open question, or calls the project MIT, is superseded.

## CI, 2026-10-02

`.github/workflows/ci.yml` installs FFmpeg and the Cairo and Pango headers,
then `requirements.txt` (Manim), and runs `tests/run.py` on Python 3.12,
`ubuntu-latest`, with full history for `tests/baseline.py`. Nothing has been
pushed, so it has not run on GitHub yet. Every job was run before committing,
from a fresh clone of this branch, the way a runner would run it: Linux jobs
in a throwaway Ubuntu 24.04 (the image `ubuntu-latest` uses) with the same
tool versions. 108 run; `test_render.py`'s real render passes.

12 of them skip: the binding tests need `../QIC` checked out and built.
`nishantmajhi/QIC` is public, but its `main` is still the pre-cleanup code (13
files differ from its `cleanup/2026-09-18`), so testing against it now would
fail for reasons in the other repository. Once that branch is merged there,
add a second checkout of it at `path: QIC` (with this repository at a sibling
path) and `make` before the tests.
