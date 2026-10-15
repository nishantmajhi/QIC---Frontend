"""
app.py — tkinter desktop app for quadratic factorization visualization.

Usage:
    python app.py

Requires:
    - libqic.dll (Windows) or libqic.so (Linux/macOS) from the QIC C project
    - manim >= 0.18  (for the animation renderer)
    - tkinter        (ships with Python on all platforms)
"""

from __future__ import annotations

import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import tkinter as tk

import factorsteps
from qic_api import parse, QuadraticExpression


# ---------------------------------------------------------------------------
# Parse-error messages
#
# The keys are the ParseError enum in QIC's include/parser.h, by value. That
# header says the values are appended and never reordered precisely so that
# this table can map them; tests/test_api.py reads the header and fails if a
# value here has no counterpart there, or the other way round, because a code
# with no entry used to fall through to a message that named nothing.
# ---------------------------------------------------------------------------

_PARSE_ERRORS = {
    1: "Invalid input — only digits, x, ^, =, +, and - are permitted.",
    2: "Missing quadratic term — equation must contain x².",
    3: "Malformed expression — check the equation structure and try again.",
    4: "Not a quadratic — the x² coefficient works out as zero.",
    5: "Coefficient out of range — values must fit in a 32-bit integer.",
    6: "The library ran out of memory while parsing that equation.",
}


# ---------------------------------------------------------------------------
# Where the videos go
#
# Manim is handed a scratch directory of its own per render and writes about
# 45 files into it — the finished MP4, one partial movie file per animation,
# and its texture cache. A 480p render measured 1.2 MB; a -qh one is several
# times that. None of it was ever removed, so every equation anyone rendered
# stayed in the temp folder for good.
#
# The finished MP4 is the only file worth keeping, so it is copied into one
# directory this app owns and the scratch directory is deleted immediately.
# Videos are not deleted on exit — the user may still be watching the one
# that was just opened, and on Windows the player holds the file open — so
# the sweep happens at startup instead, against the previous run's leftovers.
# ---------------------------------------------------------------------------

_VIDEO_DIR_NAME = "qic-frontend-videos"
_VIDEO_MAX_AGE_S = 24 * 60 * 60


def video_dir() -> str:
    """The directory finished videos are kept in, created if necessary."""
    path = os.path.join(tempfile.gettempdir(), _VIDEO_DIR_NAME)
    os.makedirs(path, exist_ok=True)
    return path


def sweep_old_videos(max_age_s: int = _VIDEO_MAX_AGE_S, now: float | None = None) -> int:
    """Delete videos left by earlier runs. Returns how many went."""
    now = time.time() if now is None else now
    removed = 0
    try:
        entries = os.listdir(video_dir())
    except OSError:
        return 0
    for name in entries:
        if not name.endswith(".mp4"):
            continue
        path = os.path.join(video_dir(), name)
        try:
            if now - os.path.getmtime(path) < max_age_s:
                continue
            os.unlink(path)
            removed += 1
        except OSError:
            # Still open in a player, or gone already. Next run will retry.
            pass
    return removed


def manim_available() -> bool:
    """
    Whether the interpreter running this app can import Manim.

    The renderer is launched as `sys.executable -m manim`, so asking this
    process is asking the exact interpreter that will be used. Without the
    check a missing Manim reaches the user as an ImportError traceback in a
    dialog rather than as a sentence about what to install.
    """
    try:
        return importlib.util.find_spec("manim") is not None
    except (ImportError, ValueError):
        return False


# ---------------------------------------------------------------------------
# Theme  —  VS Code "Default Dark Modern" / "Default Light Modern"
# ---------------------------------------------------------------------------

_DARK = dict(
    BG       = "#1E1E1E",
    BG_PANEL = "#252526",
    BG_INPUT = "#3C3C3C",
    BG_BTN   = "#373737",
    BORDER   = "#444444",
    FG       = "#D4D4D4",
    FG_DIM   = "#6A6A6A",
    FG_INPUT = "#D4D4D4",
    FG_HINT  = "#6A6A6A",
    OK       = "#4EC9B0",
    ERR      = "#F44747",
    INFO     = "#9CDCFE",
    BTN_FG   = "#D4D4D4",
    BTN_AB   = "#4EC9B0",   # active-bg on click
)

_LIGHT = dict(
    BG       = "#FFFFFF",
    BG_PANEL = "#F3F3F3",
    BG_INPUT = "#FFFFFF",
    BG_BTN   = "#E0E0E0",
    BORDER   = "#CCCCCC",
    FG       = "#333333",
    FG_DIM   = "#717171",
    FG_INPUT = "#333333",
    FG_HINT  = "#999999",
    OK       = "#007853",
    ERR      = "#CD3131",
    INFO     = "#0054A6",
    BTN_FG   = "#333333",
    BTN_AB   = "#007853",
)


def _detect_dark() -> bool:
    """Best-effort system dark-mode detection (no third-party libs)."""
    system = platform.system()
    if system == "Darwin":
        try:
            out = subprocess.check_output(
                ["defaults", "read", "-g", "AppleInterfaceStyle"],
                stderr=subprocess.DEVNULL, text=True,
            ).strip()
            return out.lower() == "dark"
        except Exception:
            return False
    if system == "Windows":
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            )
            val, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return val == 0
        except Exception:
            return False
    return False   # Linux: assume light


def _apply_dark_titlebar(window: tk.Tk) -> None:
    """Apply immersive dark title bar on Windows 10/11."""
    if platform.system() != "Windows":
        return
    try:
        import ctypes
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        value = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE,
            ctypes.byref(value), ctypes.sizeof(value),
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Platform font helpers
# ---------------------------------------------------------------------------

def _ui_font(size: int, bold: bool = False) -> tuple:
    system = platform.system()
    if system == "Windows":
        face = "Segoe UI"
    elif system == "Darwin":
        face = "SF Pro Display"
    else:
        face = "Sans"
    weight = "bold" if bold else "normal"
    return (face, size, weight)


def _mono_font(size: int) -> tuple:
    system = platform.system()
    if system == "Windows":
        face = "Cascadia Code"
    elif system == "Darwin":
        face = "SF Mono"
    else:
        face = "Monospace"
    return (face, size, "normal")


# ---------------------------------------------------------------------------
# Error dialog
# ---------------------------------------------------------------------------

class ErrorDialog(tk.Toplevel):
    def __init__(self, parent: tk.Widget, title: str, detail: str, t: dict):
        super().__init__(parent)
        self.title(title)
        self.resizable(True, True)
        self.geometry("760x480")
        self.configure(bg=t["BG_PANEL"])
        self.transient(parent)
        self.grab_set()

        # Header
        hdr = tk.Label(
            self, text=f"  {title}",
            bg=t["BG_PANEL"], fg=t["ERR"],
            font=_ui_font(10, bold=True), anchor="w",
        )
        hdr.pack(fill="x", padx=0, pady=(10, 0))

        sep = tk.Frame(self, bg=t["BORDER"], height=1)
        sep.pack(fill="x", pady=(8, 0))

        # Detail text
        err_bg = "#141414" if t is _DARK else "#FCF5F5"
        err_fg = "#CD6464" if t is _DARK else "#A01E1E"
        txt_frame = tk.Frame(self, bg=t["BG_PANEL"])
        txt_frame.pack(fill="both", expand=True, padx=12, pady=12)

        scrollbar = tk.Scrollbar(txt_frame)
        scrollbar.pack(side="right", fill="y")

        txt = tk.Text(
            txt_frame,
            wrap="none", state="normal",
            bg=err_bg, fg=err_fg,
            font=_mono_font(9),
            relief="flat", bd=0,
            yscrollcommand=scrollbar.set,
        )
        txt.insert("1.0", detail)
        txt.configure(state="disabled")
        txt.pack(side="left", fill="both", expand=True)
        scrollbar.configure(command=txt.yview)

        # Buttons
        btn_row = tk.Frame(self, bg=t["BG_PANEL"])
        btn_row.pack(fill="x", padx=12, pady=(0, 12))

        def copy_text():
            self.clipboard_clear()
            self.clipboard_append(detail)

        copy_btn = tk.Button(
            btn_row, text="Copy Output",
            command=copy_text,
            bg=t["BG_BTN"], fg=t["BTN_FG"],
            relief="flat", padx=12, pady=4,
            font=_ui_font(9), cursor="hand2",
        )
        close_btn = tk.Button(
            btn_row, text="Close",
            command=self.destroy,
            bg=t["BG_BTN"], fg=t["BTN_FG"],
            relief="flat", padx=12, pady=4,
            font=_ui_font(9), cursor="hand2",
        )
        close_btn.pack(side="right")
        copy_btn.pack(side="right", padx=(0, 8))

        self.wait_window()


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class MainApp:

    # Class-level defaults so that the close handler and the worker's
    # callback guard are safe from the moment the object exists.
    _proc = None
    _closing = False

    _INPUT_W_FRAC = 0.68
    _INPUT_W_MIN  = 320
    _INPUT_W_MAX  = 560

    def __init__(self):
        self._dark = _detect_dark()
        self._t    = _DARK if self._dark else _LIGHT

        self._root = tk.Tk()
        self._root.title("QIC Frontend")
        self._root.geometry("720x460")
        self._root.minsize(520, 360)
        self._root.configure(bg=self._t["BG"])

        _apply_dark_titlebar(self._root)
        self._build_ui()
        self._root.bind("<Configure>", self._on_resize)
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._proc = None       # the running renderer, if there is one
        self._closing = False   # set once the window is on its way out

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        t = self._t

        # Outer frame — centred vertically via pack anchor/expand
        outer = tk.Frame(self._root, bg=t["BG"])
        outer.place(relx=0.5, rely=0.5, anchor="center")

        # Menu bar — "Options" menu, flat (no submenu), default OS styling
        self._quality_var = tk.StringVar(value="ql")
        self._quality_labels = {"ql": "Low", "qm": "Medium", "qh": "High"}

        menubar = tk.Menu(self._root, tearoff=0)
        self._quality_menu = tk.Menu(
            menubar, tearoff=0,
            postcommand=self._refresh_quality_menu,
        )
        menubar.add_cascade(label="Options", menu=self._quality_menu)
        self._root.config(menu=menubar)
        self._menubar = menubar

        # Title
        tk.Label(
            outer,
            text="Quadratic Factorization Visualizer",
            bg=t["BG"], fg=t["FG"],
            font=_ui_font(22, bold=True),
        ).pack()

        # Subtitle
        tk.Label(
            outer,
            text="Enter the quadratic equation in terms of 'x'",
            bg=t["BG"], fg=t["FG_DIM"],
            font=_ui_font(11),
        ).pack(pady=(4, 28))

        # Input box
        input_w = self._clamp_input_w(720)
        self._input_var = tk.StringVar()

        input_frame = tk.Frame(
            outer,
            bg=t["BG_INPUT"],
            highlightbackground=t["BORDER"],
            highlightthickness=1,
            bd=0,
        )
        input_frame.pack()

        self._entry = tk.Entry(
            input_frame,
            textvariable=self._input_var,
            font=_mono_font(14),
            bg=t["BG_INPUT"], fg=t["FG_INPUT"],
            disabledbackground=t["BG_INPUT"], disabledforeground=t["FG_DIM"],
            insertbackground=t["FG_INPUT"],
            relief="flat", bd=8,
            width=int(input_w / 9),   # approximate char width
        )
        self._entry.pack(padx=4, pady=6, fill="x")
        self._entry.bind("<Return>", lambda _e: self._on_go())

        # Placeholder hint
        self._set_placeholder()
        self._entry.bind("<FocusIn>",  self._on_focus_in)
        self._entry.bind("<FocusOut>", self._on_focus_out)

        # Button
        self._go_btn = tk.Button(
            outer,
            text="Generate Factorization Video",
            command=self._on_go,
            bg=t["BG_BTN"], fg=t["BTN_FG"],
            activebackground=t["BTN_AB"],
            relief="flat", padx=18, pady=10,
            font=_ui_font(11, bold=True),
            cursor="hand2", bd=0,
        )
        self._go_btn.pack(pady=(16, 0))

        # Status label
        self._status_var = tk.StringVar(value="")
        self._status_lbl = tk.Label(
            outer,
            textvariable=self._status_var,
            bg=t["BG"], fg=t["FG_DIM"],
            font=_ui_font(10),
            wraplength=560,
        )
        self._status_lbl.pack(pady=(14, 0))

        # Progress bar (hidden until rendering starts)
        self._progress_frame = tk.Frame(outer, bg=t["BG"])
        self._progress_frame.pack(pady=(8, 0))
        self._progress_canvas = tk.Canvas(
            self._progress_frame,
            width=input_w, height=3,
            bg=t["BG"], highlightthickness=0,
        )
        self._progress_canvas.pack()
        self._progress_frame.pack_forget()   # hidden initially

        self._outer = outer
        self._pulse_pos   = 0
        self._pulse_dir   = 1
        self._pulse_after  = None

    # ── Placeholder text ──────────────────────────────────────────────────────

    def _set_placeholder(self):
        t = self._t
        if not self._input_var.get():
            self._entry.insert(0, "example: 2x^2+7x+3")
            self._entry.configure(fg=t["FG_HINT"])
            self._placeholder_active = True
        else:
            self._placeholder_active = False

    def _on_focus_in(self, _e=None):
        if getattr(self, "_placeholder_active", False):
            self._entry.delete(0, "end")
            self._entry.configure(fg=self._t["FG_INPUT"])
            self._placeholder_active = False

    def _on_focus_out(self, _e=None):
        if not self._input_var.get():
            self._set_placeholder()

    # ── Resize ────────────────────────────────────────────────────────────────

    def _clamp_input_w(self, frame_w: int) -> int:
        return max(self._INPUT_W_MIN,
                   min(self._INPUT_W_MAX, int(frame_w * self._INPUT_W_FRAC)))

    def _on_resize(self, _e=None):
        # <Configure> keeps arriving while the window is being torn down, by
        # which point the widgets it resizes are gone: closing the app
        # printed "invalid command name .!frame.!frame.!entry" out of a Tk
        # callback. There is nothing to resize once that has started.
        try:
            if not self._entry.winfo_exists():
                return
            fw = self._root.winfo_width()
            new_w = self._clamp_input_w(fw)
            self._progress_canvas.configure(width=new_w)
            self._entry.configure(width=max(20, int(new_w / 9)))
        except tk.TclError:
            pass

    # ── Closing ───────────────────────────────────────────────────────────────

    def _on_close(self):
        """
        Stop the renderer before the window goes.

        The render runs on a daemon thread, so closing the app abandons it —
        but the Manim process it started is a process of its own and keeps
        going, rendering a video that nothing will collect. It is terminated
        here instead.
        """
        self._closing = True
        proc = self._proc
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
            except OSError:
                pass
        self._root.destroy()

    def _post(self, callback, *args):
        """Hand a result back to the UI thread, unless the UI has gone."""
        if self._closing:
            return
        self._root.after(0, callback, *args)

    # ── Status helpers ────────────────────────────────────────────────────────

    def _set_status(self, msg: str, color: str | None = None):
        self._status_var.set(msg)
        self._status_lbl.configure(fg=color or self._t["FG_DIM"])

    def _refresh_quality_menu(self):
        menu = self._quality_menu
        menu.delete(0, "end")
        menu.add_command(label="Render Quality", state="disabled")
        chosen = self._quality_var.get()
        for flag, label in self._quality_labels.items():
            mark = "\u2713  " if flag == chosen else "     "
            menu.add_command(
                label=f"{mark}{label}",
                command=lambda f=flag: self._quality_var.set(f),
            )

    def _lock(self):
        self._go_btn.configure(state="disabled", cursor="watch")
        self._entry.configure(state="disabled")
        self._menubar.entryconfig("Options", state="disabled")
        self._progress_frame.pack(pady=(8, 0))
        self._start_pulse()

    def _unlock(self):
        self._stop_pulse()
        self._progress_frame.pack_forget()
        self._go_btn.configure(state="normal", cursor="hand2")
        self._entry.configure(state="normal")
        self._menubar.entryconfig("Options", state="normal")

    # ── Pulsing progress bar ──────────────────────────────────────────────────

    def _start_pulse(self):
        self._pulse_pos = 0
        self._pulse_dir = 1
        self._do_pulse()

    def _do_pulse(self):
        c  = self._progress_canvas
        w  = int(c.cget("width"))
        bw = max(60, w // 4)

        c.delete("all")
        c.create_rectangle(
            self._pulse_pos, 0,
            self._pulse_pos + bw, 3,
            fill=self._t["INFO"], width=0,
        )

        self._pulse_pos += self._pulse_dir * 8
        if self._pulse_pos + bw >= w:
            self._pulse_dir = -1
        elif self._pulse_pos <= 0:
            self._pulse_dir = 1

        self._pulse_after = self._root.after(40, self._do_pulse)

    def _stop_pulse(self):
        if self._pulse_after:
            self._root.after_cancel(self._pulse_after)
            self._pulse_after = None
        self._progress_canvas.delete("all")

    # ── Main action ───────────────────────────────────────────────────────────

    def _on_go(self):
        # Clear placeholder before reading
        if getattr(self, "_placeholder_active", False):
            self._set_status("Equation not found!", self._t["ERR"])
            return

        eq = self._entry.get().strip()
        if not eq:
            self._set_status("Equation not found!", self._t["ERR"])
            return

        try:
            result: QuadraticExpression = parse(eq)
        except FileNotFoundError as exc:
            self._set_status(str(exc), self._t["ERR"])
            return

        if result.error:
            msg = _PARSE_ERRORS.get(result.error,
                                    "Parse error — check the equation and retry.")
            self._set_status(msg, self._t["ERR"])
            return

        a, b, c = result.a, result.b, result.c
        if a == 0:
            self._set_status(
                "Coefficient a = 0 — expression is not quadratic.", self._t["ERR"]
            )
            return

        self._set_status(
            f"Accepted:  {a}x² {b:+}x {c:+} = 0   —   Rendering animation…",
            self._t["INFO"],
        )
        quality = self._quality_var.get()
        self._lock()
        if not manim_available():
            self._show_text_factorization(a, b, c)
            return
        threading.Thread(target=self._render, args=(a, b, c, quality), daemon=True).start()

    # ── Manim render (background thread) ─────────────────────────────────────

    def _render(self, a: int, b: int, c: int, quality: str):
        # Anything raised in here used to end the worker thread silently with
        # the window still locked: the button disabled, the entry disabled and
        # the progress bar pulsing with nothing behind it. The only way out
        # was to close the app. Every path now reports through _on_fail, which
        # unlocks.
        try:
            self._do_render(a, b, c, quality)
        except Exception:
            self._root.after(
                0, self._on_fail,
                "The renderer could not be started.\n\n" + traceback.format_exc(),
            )

    def _do_render(self, a: int, b: int, c: int, quality: str):
        cfg_path  = None
        media_dir = None
        try:
            with tempfile.NamedTemporaryFile(
                suffix=".json", delete=False, mode="w", prefix="qic_cfg_",
                encoding="utf-8",
            ) as fh:
                json.dump({"a": a, "b": b, "c": c}, fh)
                cfg_path = fh.name

            env            = os.environ.copy()
            env["QIC_FACTOR_CONFIG"] = cfg_path

            here      = os.path.dirname(os.path.abspath(__file__))
            script    = os.path.join(here, "factorize.py")
            media_dir = tempfile.mkdtemp(prefix="qic_manim_")

            cmd = [
                sys.executable, "-m", "manim",
                script, "FactorizationScene",
                f"-{quality}",
                "--media_dir", media_dir,
            ]

            # Popen rather than run, so that closing the window can stop it.
            # A render is half a minute of full-speed CPU at the default
            # quality and minutes at the highest; with subprocess.run there
            # was no handle to terminate, and quitting the app left Manim
            # running to finish a video nothing would ever collect.
            proc = subprocess.Popen(
                cmd, env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self._proc = proc
            stdout, stderr = proc.communicate()

            if self._closing:
                return

            if proc.returncode != 0:
                combined = ""
                if stderr.strip():
                    combined += "--- stderr ---\n" + stderr.strip() + "\n\n"
                if stdout.strip():
                    combined += "--- stdout ---\n" + stdout.strip()
                self._post(self._on_fail,
                           combined.strip() or "Renderer exited with no output.")
                return

            mp4 = _find_video(media_dir)
            if not mp4:
                self._post(
                    self._on_fail,
                    "Renderer completed successfully but no video file was produced.\n\n"
                    + stdout.strip(),
                )
                return

            # Copy the deliverable out before the scratch directory goes.
            kept = os.path.join(
                video_dir(),
                f"factorization_{a}_{b:+}_{c:+}_{quality}_{int(time.time())}.mp4",
            )
            shutil.copyfile(mp4, kept)

        finally:
            self._proc = None
            if cfg_path:
                try:
                    os.unlink(cfg_path)
                except OSError:
                    pass
            if media_dir:
                shutil.rmtree(media_dir, ignore_errors=True)

        self._post(self._on_done, kept)

    # ── Text fallback (no renderer installed) ────────────────────────────────

    def _show_text_factorization(self, a: int, b: int, c: int):
        """
        Show the working as text.

        Manim is a large install with native dependencies, and without it the
        app had no output path at all: it shelled out anyway and showed the
        user ModuleNotFoundError in a scrollable box. The algebra does not
        need a renderer, so it is shown directly and the app says why.
        """
        self._unlock()
        self._set_status(
            "Manim is not installed — showing the working as text.", self._t["INFO"]
        )
        detail = (
            factorsteps.as_text(a, b, c)
            + "\n\n"
            + "─" * 60
            + "\n"
            + "No video was rendered: this Python has no 'manim' module.\n"
            + f"Install it with:  {sys.executable} -m pip install -r requirements.txt\n"
            + "Manim also needs FFmpeg on PATH."
        )
        ErrorDialog(self._root, "Factorization (no renderer)", detail, self._t)

    # ── Render callbacks (main thread) ────────────────────────────────────────

    def _on_done(self, video_path: str):
        self._unlock()
        # os.startfile raises when nothing is associated with .mp4, and this
        # runs inside a Tk callback, where an exception is printed to a
        # console the user of a windowed app does not have. The status line
        # said "opening video" and nothing opened.
        try:
            _open_file(video_path)
        except OSError as exc:
            self._set_status(
                f"✓  Render complete — could not open the player ({exc.strerror or exc}).",
                self._t["OK"],
            )
            ErrorDialog(
                self._root, "Video ready",
                "The video was rendered but this system could not open it "
                "automatically.\n\nIt is here:\n\n" + video_path,
                self._t,
            )
            return
        self._set_status("✓  Render complete — opening video.", self._t["OK"])

    def _on_fail(self, detail: str):
        self._unlock()
        self._set_status(
            "Render failed — review the error report for details.", self._t["ERR"]
        )
        ErrorDialog(self._root, "Renderer Error", detail, self._t)

    # ── Run ───────────────────────────────────────────────────────────────────

    def run(self):
        self._root.mainloop()


# ---------------------------------------------------------------------------
# Cross-platform file opener
# ---------------------------------------------------------------------------

def _open_file(path: str):
    system = platform.system()
    if system == "Windows":
        os.startfile(path)
    elif system == "Darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


def _find_video(media_dir: str) -> str | None:
    """
    The finished scene file inside a Manim media directory.

    Manim writes one MP4 per animation into `partial_movie_files/` — 27 of
    them for this scene — alongside the single combined file. Walking for the
    first `.mp4` happened to find the right one because the combined file sits
    in the shallower directory, but that is an accident of traversal order;
    the partials are excluded by name instead.
    """
    best = None
    for root_dir, _, files in os.walk(media_dir):
        if "partial_movie_files" in root_dir.replace("\\", "/").split("/"):
            continue
        for fname in files:
            if not fname.endswith(".mp4"):
                continue
            path = os.path.join(root_dir, fname)
            depth = path.count(os.sep)
            if best is None or depth < best[0]:
                best = (depth, path)
    return best[1] if best else None


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    sweep_old_videos()
    MainApp().run()


if __name__ == "__main__":
    main()
