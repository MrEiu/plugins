"""
Native Embedded Terminal Widget for Kapsel TUI.
Bridges pyte VT100 emulator with winpty (Windows) and ptyprocess (POSIX).
All comments and docstrings are in English.
"""

from __future__ import annotations

import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import threading
import time
from typing import Callable, Dict, List, Optional, Tuple

import pyte
from rich.style import Style
from rich.text import Text
from textual.events import Key, Resize
from textual.widget import Widget

from kapsel.core.tools.process import kill_process_tree

# PTY drivers import
_HAS_WINPTY = False
_HAS_PTYPROCESS = False

try:
    if sys.platform == "win32":
        from winpty import PtyProcess as WinPtyProcess
        _HAS_WINPTY = True
    else:
        import ptyprocess
        _HAS_PTYPROCESS = True
except ImportError:
    pass


# ANSI 16-color palette mapping for pyte
COLOR_MAP = {
    "black": "#1e1e1e",
    "red": "#f43f5e",
    "green": "#10b981",
    "brown": "#eab308",
    "blue": "#38bdf8",
    "magenta": "#a855f7",
    "cyan": "#06b6d4",
    "white": "#e6edf3",
    "brightblack": "#4b5563",
    "brightred": "#fb7185",
    "brightgreen": "#34d399",
    "brightbrown": "#fde047",
    "brightblue": "#60a5fa",
    "brightmagenta": "#c084fc",
    "brightcyan": "#22d3ee",
    "brightwhite": "#ffffff",
    "default": "#e6edf3",
}


def _resolve_default_shell() -> Tuple[str, List[str]]:
    """Resolves host default shell command and arguments."""
    if sys.platform == "win32":
        for candidate in ("pwsh.exe", "powershell.exe", "cmd.exe"):
            found = shutil.which(candidate)
            if found:
                return found, [found, "-NoLogo"] if "power" in candidate.lower() or "pwsh" in candidate.lower() else [found]
        return "cmd.exe", ["cmd.exe"]
    else:
        shell = os.environ.get("SHELL") or shutil.which("zsh") or shutil.which("bash") or "/bin/sh"
        return shell, [shell]


class TerminalWidget(Widget):
    """
    Embedded interactive terminal emulator widget.
    Maintains a 2D ANSI character matrix via pyte and connects to native PTY.
    """

    can_focus = True

    def __init__(
        self,
        cwd: Optional[Path] = None,
        env: Optional[Dict[str, str]] = None,
        on_title_change: Optional[Callable[[str], None]] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.cwd = cwd or Path.cwd()
        self.env = env or dict(os.environ)
        self.on_title_change = on_title_change

        self.cols: int = 80
        self.rows: int = 24

        # Pyte VT100 Screen and Stream
        self.vt_screen = pyte.Screen(self.cols, self.rows)
        self.vt_screen.set_mode(pyte.modes.LNM)
        self.vt_stream = pyte.Stream(self.vt_screen)

        # Process & Thread Handles
        self._pty_proc: Optional[Any] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._running = False
        self._pid: Optional[int] = None

    def on_mount(self) -> None:
        """Starts the PTY session when the widget is mounted."""
        self._start_pty()

    def on_click(self) -> None:
        """Focuses terminal upon clicking."""
        self.focus()

    def on_unmount(self) -> None:
        """Terminates the PTY session on unmount."""
        self.terminate()

    def _start_pty(self) -> None:
        """Spawns background PTY process and launches asynchronous stream reader."""
        shell_bin, shell_args = _resolve_default_shell()
        self.cols = max(20, self.size.width or 80)
        self.rows = max(5, self.size.height or 24)

        self.vt_screen.resize(self.rows, self.cols)
        self._running = True

        try:
            if sys.platform == "win32" and _HAS_WINPTY:
                self._pty_proc = WinPtyProcess.spawn(
                    shell_args,
                    cwd=str(self.cwd),
                    env=self.env,
                    dimensions=(self.rows, self.cols),
                )
                self._pid = getattr(self._pty_proc, "pid", None)
                # Send initial Device Attributes handshake for ConPTY
                self.write_input("\x1b[?1;0c")
            elif _HAS_PTYPROCESS:
                self._pty_proc = ptyprocess.PtyProcessUnicode.spawn(
                    shell_args,
                    cwd=str(self.cwd),
                    env=self.env,
                    dimensions=(self.rows, self.cols),
                    dimensions_as_lines_cols=True,
                )
                self._pid = getattr(self._pty_proc, "pid", None)
            else:
                # Subprocess fallback if no PTY is available
                self._pty_proc = subprocess.Popen(
                    shell_args,
                    cwd=str(self.cwd),
                    env=self.env,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    bufsize=0,
                )
                self._pid = self._pty_proc.pid

            # Launch reader thread
            self._reader_thread = threading.Thread(target=self._read_loop, daemon=True)
            self._reader_thread.start()

        except Exception as e:
            pass

    def _read_loop(self) -> None:
        """Continuously reads PTY stdout bytes and feeds them to pyte."""
        while self._running and self._pty_proc:
            try:
                raw: Optional[str] = None
                if sys.platform == "win32" and _HAS_WINPTY:
                    raw = self._pty_proc.read(4096)
                elif _HAS_PTYPROCESS:
                    raw = self._pty_proc.read(4096)
                elif hasattr(self._pty_proc, "stdout") and self._pty_proc.stdout:
                    chunk = self._pty_proc.stdout.read(1024)
                    if chunk:
                        raw = chunk.decode("utf-8", errors="replace")

                if raw:
                    # Automatic ConPTY / VT DA query response
                    if "\x1b[c" in raw:
                        self.write_input("\x1b[?1;0c")

                    self.vt_stream.feed(raw)
                    self.app.call_from_thread(self.refresh)
                else:
                    time.sleep(0.01)
            except (EOFError, OSError):
                break
            except Exception:
                time.sleep(0.01)

    def write_input(self, text: str) -> None:
        """Sends keystrokes or text string to the PTY process."""
        if not self._pty_proc or not self._running:
            return

        try:
            if sys.platform == "win32" and _HAS_WINPTY:
                self._pty_proc.write(text)
            elif _HAS_PTYPROCESS:
                self._pty_proc.write(text)
            elif hasattr(self._pty_proc, "stdin") and self._pty_proc.stdin:
                self._pty_proc.stdin.write(text.encode("utf-8"))
                self._pty_proc.stdin.flush()
        except Exception:
            pass

    def on_resize(self, event: Resize) -> None:
        """Handles widget resizing and propagates new dimensions to PTY."""
        new_cols = max(20, event.size.width)
        new_rows = max(5, event.size.height)

        if new_cols != self.cols or new_rows != self.rows:
            self.cols = new_cols
            self.rows = new_rows
            self.vt_screen.resize(self.rows, self.cols)

            try:
                if self._pty_proc and hasattr(self._pty_proc, "setwinsize"):
                    self._pty_proc.setwinsize(self.rows, self.cols)
            except Exception:
                pass

    def on_key(self, event: Key) -> None:
        """Translates Textual key events into terminal ANSI sequences."""
        key_name = event.key.lower()

        # If Tab key is pressed, let it bubble to App for Tab Leader switching
        if key_name == "tab":
            return

        KEY_MAP = {
            "enter": "\r",
            "return": "\r",
            "space": " ",
            "backspace": "\x08" if sys.platform == "win32" else "\x7f",
            "escape": "\x1b",
            "up": "\x1b[A",
            "down": "\x1b[B",
            "right": "\x1b[C",
            "left": "\x1b[D",
            "home": "\x1b[H",
            "end": "\x1b[F",
            "pageup": "\x1b[5~",
            "pagedown": "\x1b[6~",
            "delete": "\x1b[3~",
            "insert": "\x1b[2~",
            "ctrl+c": "\x03",
            "ctrl+d": "\x04",
            "ctrl+l": "\x0c",
            "ctrl+z": "\x1a",
            "ctrl+a": "\x01",
            "ctrl+e": "\x05",
            "ctrl+u": "\x15",
            "ctrl+k": "\x0b",
        }

        if key_name in KEY_MAP:
            self.write_input(KEY_MAP[key_name])
            event.stop()
        elif event.character:
            self.write_input(event.character)
            event.stop()

    def render(self) -> Text:
        """Renders the pyte 2D character matrix into Rich Text."""
        result = Text()
        cursor_x = self.vt_screen.cursor.x
        cursor_y = self.vt_screen.cursor.y

        for y in range(self.rows):
            line_text = Text()
            for x in range(self.cols):
                char = self.vt_screen.buffer[y][x]
                ch = char.data if char.data else " "

                # Style properties
                fg = COLOR_MAP.get(char.fg, "#e6edf3") if char.fg != "default" else "#e6edf3"
                bg = COLOR_MAP.get(char.bg, None) if char.bg != "default" else None

                # Cursor display (solid block at cursor position)
                if x == cursor_x and y == cursor_y and self.has_focus:
                    fg = "#080c10"
                    bg = "#38bdf8"

                style = Style(
                    color=fg,
                    bgcolor=bg,
                    bold=char.bold,
                    italic=char.italics,
                    underline=char.underscore,
                    reverse=char.reverse,
                )
                line_text.append(ch, style=style)

            result.append_text(line_text)
            if y < self.rows - 1:
                result.append("\n")

        return result

    def terminate(self) -> None:
        """Terminates the PTY process and all child processes recursively."""
        self._running = False
        if self._pid:
            try:
                kill_process_tree(self._pid, timeout=0.3)
            except Exception:
                pass
        self._pty_proc = None
