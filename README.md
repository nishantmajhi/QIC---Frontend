# QIC Frontend

A desktop app that takes a quadratic equation and produces a short video
working through its factorization, one step at a time.

You type `2x^2+7x+3`. It answers with about half a minute of animation:
check the discriminant, split the middle term, group, factor each group,
take out the common bracket, and land on `(2x + 1)(x + 3) = 0`.

The parsing is done by [QIC](../QIC), a C library that lives next door. The
animation is done by [Manim](https://www.manim.community/). This project is
the window in between, plus the algebra that decides what each frame says.

---

## What you need

| | | |
| --- | --- | --- |
| **Python 3.10+** | required | `tkinter` ships with it on all platforms |
| **The QIC library** | required | `libqic.dll` or `libqic.so`, built from the sibling project |
| **Manim 0.18.x** | optional | `pip install -r requirements.txt` |
| **FFmpeg** | with Manim | must be on `PATH`; pip cannot install it |

Without Manim the app still works: it shows the same working as text instead
of rendering it. Without the QIC library it cannot start a factorization at
all, and says so with the command that builds it.

### Build the library first

The shared library is a build artefact and is **not** committed, so a fresh
clone has to build it:

```sh
cd ../QIC
make            # Linux, macOS
mingw32-make    # Windows, MinGW
```

That leaves `libqic.dll` (plus `libqic.dll.a`) or `libqic.so` in `QIC/`,
which is one of the three places this app looks:

1. beside `app.py`
2. its parent directory
3. `../QIC/`

The third is where `make` already puts it, so no copying is needed if the two
project folders are left side by side.

### Install the renderer

```sh
pip install -r requirements.txt
```

`requirements.txt` pins Manim to the 0.18 series. Its scene API moves between
minor versions and `factorize.py` is written against that one.

Manim needs FFmpeg to combine the animation into an MP4. It is not a Python
package: install it from your package manager, or from
[ffmpeg.org](https://ffmpeg.org/download.html), and make sure `ffmpeg` runs
from a terminal before expecting a video.

---

## Running it

```sh
python app.py
```

Type an equation and press Enter or the button. Accepted forms:

```
2x^2+7x+3
x^2 - 5x + 6 = 0
-2x^2 + 4x - 2
6x^2-x-2=0
```

Whitespace and case are handled inside the library. Only digits, `x`, `^`,
`=`, `+` and `-` are allowed; anything else is rejected with a message
naming the rule it broke.

**Render quality** is under the Options menu: Low (480p, about half a minute),
Medium (720p) and High (1080p, several minutes). Low is the default and is
readable.

### Where the videos go

Finished videos are kept in `qic-frontend-videos` inside your system temp
directory, named for the coefficients and the time. The app opens each one in
whatever plays MP4s on your system.

Manim writes far more than the video — a fragment per animation, plus its
caches, about 45 files and 1.2 MB for a single 480p render. That goes into a
scratch directory which is deleted as soon as the video has been copied out,
whether the render succeeded or failed.

Videos themselves are not deleted when the app closes, because you may still
be watching one. They are swept on the next launch, once they are more than a
day old.

Closing the window during a render stops the renderer with it.

### Without Manim

If the Python running the app cannot import Manim, the app does not shell out
and fail. It shows the same factorization as text, with the steps and the
notes the video would have narrated, and tells you what to install. This is
checked before each render rather than guessed at startup, so installing
Manim and pressing the button again is enough.

---

## The maths

For `ax² + bx + c`, the method is to split the middle term into two whose sum
is `b` and whose product is `ac`:

```
p = (b + √Δ) / 2        q = (b − √Δ) / 2        Δ = b² − 4ac
```

Those are whole numbers exactly when `Δ` is a perfect square, which is why the
video checks the discriminant first and stops there when it is not.

Then, with `g = gcd(a, p)`, `a₂ = a/g`, `p₂ = p/g` and `q₂ = q/a₂`:

```
ax² + px + qx + c
= gx(a₂x + p₂) + q₂(a₂x + p₂)
= (gx + q₂)(a₂x + p₂)
```

Every one of those divisions is exact. `g` divides `a` and `p` by
construction; `a₂` divides `q` because `p₂q = a₂c` with `gcd(a₂, p₂) = 1`.
`p` is chosen as whichever root shares the larger factor with `a`, which is
what keeps the grouping step in whole numbers.

Two cases do not fit the pattern and are handled separately:

- **`a < 0`** — the whole equation is multiplied by −1 first, and the video
  says so. `−x² + 5x − 6` and `x² − 5x + 6` factor to the same brackets.
- **`c = 0`** — there is nothing to split, because `x` is already a common
  factor of every term: `3x² + 6x = (3x)(x + 2)`. The video takes the common
  factor out in one step instead of pretending to split a middle term.

---

## Layout

```
QIC - Frontend/
├── app.py              the window, the render pipeline, the temp files
├── factorsteps.py      the factorization and every string it produces
├── factorize.py        the Manim scene: what moves, in what colour
├── qic_api.py          ctypes wrapper around libqic
├── requirements.txt
└── tests/
    ├── run.py          the whole suite
    ├── fakemanim.py    a stand-in for Manim that records instead of drawing
    ├── scenerun.py     plays a scene and reads back what it drew
    ├── baseline.py     imports the pre-cleanup code out of git
    ├── appstub.py      drives the render pipeline without a window
    ├── test_steps.py   the maths and the equations it renders
    ├── test_scene.py   what the video shows, in order
    ├── test_app.py     the pipeline, the temp files, the status line
    ├── test_api.py     the ctypes boundary and the C error codes
    ├── test_original.py  the defects this suite was written against
    └── test_render.py  one real render, end to end
```

`factorsteps.py` imports nothing but `math`. Everything that decides what the
video says is in there, which is why it can be tested exhaustively and why
the text fallback and the animation can never disagree: they are the same
function.

`app.py` launches the renderer as `sys.executable -m manim`, passing the
coefficients through a temporary JSON file named by the `QIC_FACTOR_CONFIG`
environment variable rather than on the command line. Nothing the user types
reaches a shell.

---

## Tests

```sh
python tests/run.py           # everything
python tests/run.py steps     # one module
```

108 checks, no test framework to install — everything is `unittest` from the
standard library.

Most of them replace Manim with `tests/fakemanim.py`, which records the text
of everything the scene draws instead of rendering it. That makes the
assertions about the video assertions about what a viewer reads, and it keeps
the suite at about three seconds.

`tests/test_render.py` does one real render with the real Manim and the real
FFmpeg, and checks the MP4 exists, is a video, and left no scratch directory
behind. It reports as skipped when Manim is not installed; the run prints why.
With it, the suite takes about a minute and a half.

`tests/test_original.py` asserts that the defects this pass fixed were
present in the code before it, reading that code out of the repository's
first commit rather than a transcription of it.

---

## Known limitations

- **A render cannot be cancelled without closing the window.** There is no
  Cancel button. Closing does stop the renderer, so nothing is left running.
- **The progress bar does not know how far along it is.** Manim reports
  progress on its own stdout, which is captured rather than parsed, so the
  bar pulses rather than filling.
- **Very large coefficients are refused by the library, not by the app.**
  Anything that does not fit in a 32-bit integer comes back as a parse error.
- **The video is whatever your system opens MP4s with.** If nothing is
  associated, the app says where the file is instead.

---

## Licence

Free for personal, non-commercial use. You may use, study and modify this
software for yourself, but you may not use it commercially, and you may not
share or publish it, in its original form or modified. See [LICENSE](LICENSE)
for the full terms.
