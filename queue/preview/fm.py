"""
Native Interactive 3-Column Miller Columns File Manager (fm) for Kapsel.
Built 100% on prompt_toolkit with zero external dependencies:
- Column 1: Parent directory
- Column 2: Current directory with cursor and file metadata
- Column 3: Real-time file / directory preview
Keyboard Navigation:
  [h / Left]       Ascend to parent directory
  [j / Down]       Move selection down
  [k / Up]         Move selection up
  [l / Right]      Enter directory or open file
  [Enter]          Exit and cd into current / selected directory
  [c / y]          Copy selected path to clipboard
  [q / Esc]        Quit without changing directory

All comments and descriptions are in English.
"""

from pathlib import Path
import os
import shutil
import subprocess
import sys
import time
from typing import Dict, List, Optional, Tuple

from prompt_toolkit.application import Application
from prompt_toolkit.formatted_text import ANSI, to_formatted_text
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import HSplit, Layout, VSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.styles import Style

from kapsel.ui.prompt import copy_to_clipboard, get_safe_output


FM_STYLE = Style.from_dict({
    "fm.header": "bold #00f0ff bg:#181825",
    "fm.header_path": "bold #f8fafc bg:#181825",
    "fm.header_stat": "dim #38bdf8 bg:#181825",
    "fm.footer": "dim #94a3b8 bg:#181825",
    "fm.footer_key": "bold #38bdf8 bg:#181825",
    "fm.footer_copied": "bold #10b981 bg:#181825",
    "fm.parent_dir": "dim #38bdf8",
    "fm.parent_file": "dim #64748b",
    "fm.parent_curr": "bold #00f0ff bg:#282a36",
    "fm.item_dir": "bold #38bdf8",
    "fm.item_file": "#e2e8f0",
    "fm.item_cursor": "bold #10b981",
    "fm.item_selected": "bold #ffffff bg:#334155",
    "fm.item_selected_dir": "bold #38bdf8 bg:#334155",
    "fm.size": "dim #94a3b8",
    "fm.preview_header": "bold #a855f7 bg:#1e1e2e",
    "fm.preview_text": "#cbd5e1",
    "fm.preview_lineno": "dim #64748b",
    "fm.preview_dir_head": "bold #38bdf8",
    "fm.preview_dir_item": "#94a3b8",
    "fm.border": "dim #475569",
})


def get_file_icon(path: Path) -> str:
    """Returns a modern glyph icon based on file type."""
    try:
        if path.is_dir():
            return "📁"
        s = path.suffix.lower()
        if s in (".py", ".rs", ".go", ".js", ".ts", ".c", ".cpp", ".java", ".sh", ".bash", ".ps1"):
            return "💻"
        if s in (".md", ".txt", ".rst", ".doc", ".docx"):
            return "📄"
        if s in (".json", ".yaml", ".yml", ".toml", ".xml"):
            return "⚙️"
        if s in (".csv", ".tsv", ".xlsx"):
            return "📊"
        if s in (".zip", ".tar", ".gz", ".7z", ".rar", ".whl"):
            return "📦"
        if s in (".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif", ".ico", ".bmp"):
            return "🖼️"
        if s == ".pdf":
            return "📕"
        if s in (".mp4", ".mkv", ".mp3", ".wav", ".flac", ".ogg", ".avi"):
            return "🎵"
        if s in (".exe", ".dll", ".so", ".bin", ".pyc"):
            return "⚙️"
    except Exception:
        pass
    return "📄"


def format_size(size_bytes: int) -> str:
    """Formats raw byte count into human-readable compact representation."""
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f}K"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f}M"
    return f"{size_bytes / (1024 * 1024 * 1024):.1f}G"


def open_file_externally(path: Path) -> None:
    """Opens a file using user's preferred editor or system default application."""
    editor = os.environ.get("EDITOR") or os.environ.get("VISUAL")
    if editor:
        try:
            subprocess.run([editor, str(path)])
            return
        except Exception:
            pass

    try:
        if sys.platform == "win32":
            os.startfile(str(path))
        elif sys.platform == "darwin":
            subprocess.run(["open", str(path)])
        else:
            subprocess.run(["xdg-open", str(path)])
    except Exception:
        pass


ARCHIVE_EXTENSIONS = (
    ".zip", ".tar", ".gz", ".tgz", ".bz2", ".tbz2", ".xz", ".txz",
    ".7z", ".rar", ".whl", ".jar", ".iso", ".apk", ".zst",
)

IMAGE_EXTENSIONS = (
    ".png", ".jpg", ".jpeg", ".webp", ".gif", ".ico", ".bmp", ".tiff", ".svg", ".avif", ".heic", ".jxl",
)


def _get_archive_entries(archive_path: Path) -> Optional[List[Tuple[str, int, bool]]]:
    """
    Extracts member entries (name, size, is_dir) from zip, 7z, tar, and other archives
    using 7z/tar tools or Python's standard zipfile/tarfile modules.
    """
    suffix = archive_path.suffix.lower()

    # 1. Native zipfile for standard zip, whl, jar, apk
    if suffix in (".zip", ".whl", ".jar", ".apk"):
        try:
            import zipfile
            if zipfile.is_zipfile(archive_path):
                with zipfile.ZipFile(archive_path, "r") as zf:
                    results = []
                    for info in zf.infolist():
                        if info.filename.startswith("__MACOSX"):
                            continue
                        results.append((info.filename, info.file_size, info.is_dir()))
                    return results
        except Exception:
            pass

    # 2. Dedicated CLI archive tool (7zz / 7z)
    tool_7z = shutil.which("7zz") or shutil.which("7z")
    if not tool_7z:
        for candidate in [
            Path(os.environ.get("WINDIR", "C:\\WINDOWS")) / "system32" / "7z.exe",
            Path(os.environ.get("USERPROFILE", Path.home())) / "scoop" / "shims" / "7z.exe",
            Path(os.environ.get("USERPROFILE", Path.home())) / ".kapsel" / "bin" / "7z.exe",
        ]:
            if candidate.exists():
                tool_7z = str(candidate)
                break

    if tool_7z:
        try:
            p = subprocess.run(
                [tool_7z, "l", "-sccUTF-8", "-xr!__MACOSX", str(archive_path)],
                capture_output=True,
                timeout=6,
            )
            if p.returncode == 0:
                out = p.stdout.decode("utf-8", errors="replace")
                lines = out.splitlines()
                in_table = False
                results = []
                for line in lines:
                    if line.startswith("-------------------"):
                        in_table = not in_table
                        continue
                    if in_table and len(line) >= 53:
                        attr = line[20:25]
                        is_dir = "D" in attr
                        try:
                            size = int(line[26:38].strip())
                        except ValueError:
                            size = 0
                        name = line[53:].strip()
                        if name:
                            results.append((name, size, is_dir))
                if results:
                    return results
        except Exception:
            pass

    # 3. Native tarfile for tar, tar.gz, tgz, etc.
    if suffix in (".tar", ".gz", ".tgz", ".bz2", ".tbz2", ".xz", ".txz"):
        try:
            import tarfile
            if tarfile.is_tarfile(archive_path):
                with tarfile.open(archive_path, "r:*") as tf:
                    results = []
                    for member in tf.getmembers():
                        if member.name.startswith("__MACOSX"):
                            continue
                        results.append((member.name, member.size, member.isdir()))
                    return results
        except Exception:
            pass

    return None


class FileManagerApp:
    """
    Stateful interactive 3-column Miller Columns file manager.
    Zero external dependencies, instant rendering.
    """

    def __init__(self, initial_target: Optional[Path] = None):
        target = (initial_target or Path.cwd()).resolve()
        initial_file_focus: Optional[str] = None

        if target.is_file():
            self.current_dir = target.parent
            initial_file_focus = target.name
        elif target.is_dir():
            self.current_dir = target
        else:
            self.current_dir = Path.cwd().resolve()

        self.target_cd: Optional[Path] = None
        self.selected_idx: int = 0
        self.current_items: List[Path] = []
        self.parent_items: List[Path] = []
        self.preview_cache: Dict[str, List[Tuple[str, str]]] = {}
        self.status_message: str = ""
        self._last_move_time: float = 0.0
        self._last_move_dir: str = ""
        self._consecutive_move_count: int = 0
        self.app: Optional[Application] = None

        self.refresh_items()

        # Focus initial target file if provided
        if initial_file_focus:
            for i, p in enumerate(self.current_items):
                if p.name == initial_file_focus:
                    self.selected_idx = i
                    break

    def refresh_items(self) -> None:
        """Scans current and parent directories, caching sorted items."""
        # 1. Current directory items
        try:
            dirs = []
            files = []
            for item in self.current_dir.iterdir():
                try:
                    if item.is_dir():
                        dirs.append(item)
                    else:
                        files.append(item)
                except Exception:
                    files.append(item)
            dirs.sort(key=lambda x: x.name.lower())
            files.sort(key=lambda x: x.name.lower())
            self.current_items = dirs + files
        except Exception:
            self.current_items = []

        # Bound check selected index
        if not self.current_items:
            self.selected_idx = 0
        else:
            self.selected_idx = max(0, min(self.selected_idx, len(self.current_items) - 1))

        # 2. Parent directory items
        parent_dir = self.current_dir.parent
        if parent_dir != self.current_dir and parent_dir.exists():
            try:
                p_dirs = []
                p_files = []
                for item in parent_dir.iterdir():
                    try:
                        if item.is_dir():
                            p_dirs.append(item)
                        else:
                            p_files.append(item)
                    except Exception:
                        p_files.append(item)
                p_dirs.sort(key=lambda x: x.name.lower())
                p_files.sort(key=lambda x: x.name.lower())
                self.parent_items = p_dirs + p_files
            except Exception:
                self.parent_items = []
        else:
            self.parent_items = []

    def get_selected_item(self) -> Optional[Path]:
        """Returns currently highlighted item in middle column."""
        if 0 <= self.selected_idx < len(self.current_items):
            return self.current_items[self.selected_idx]
        return None

    def _calculate_step(self, direction: str) -> int:
        """
        Calculates dynamic acceleration step for rapid continuous up/down movements.
        Single tap = 1 step. Rapid double-tap or hold (<0.35s) immediately accelerates to 3, 5, 8 steps.
        """
        now = time.time()
        # If pressed within 0.35s in the same direction, count as continuous/rapid repeat
        if direction == self._last_move_dir and (now - self._last_move_time) < 0.35:
            self._consecutive_move_count += 1
        else:
            self._consecutive_move_count = 0

        self._last_move_time = now
        self._last_move_dir = direction

        if self._consecutive_move_count >= 3:
            return 8
        elif self._consecutive_move_count == 2:
            return 5
        elif self._consecutive_move_count == 1:
            return 3
        return 1

    def move_up(self, step: Optional[int] = None) -> None:
        """Moves cursor up in current directory with continuous rapid acceleration."""
        self.status_message = ""
        if not self.current_items:
            return
        actual_step = step if step is not None else self._calculate_step("up")
        self.selected_idx = max(0, self.selected_idx - actual_step)
        if self.app:
            self.app.invalidate()

    def move_down(self, step: Optional[int] = None) -> None:
        """Moves cursor down in current directory with continuous rapid acceleration."""
        self.status_message = ""
        if not self.current_items:
            return
        actual_step = step if step is not None else self._calculate_step("down")
        self.selected_idx = min(len(self.current_items) - 1, self.selected_idx + actual_step)
        if self.app:
            self.app.invalidate()

    def enter_dir_or_open(self) -> None:
        """Enters directory or opens file (strictly single-step point navigation)."""
        self.status_message = ""
        self._consecutive_move_count = 0
        selected = self.get_selected_item()
        if not selected:
            return

        if selected.is_dir():
            self.current_dir = selected.resolve()
            self.selected_idx = 0
            self.refresh_items()
            if self.app:
                self.app.invalidate()
        else:
            open_file_externally(selected)

    def ascend_to_parent(self) -> None:
        """Ascends to parent directory (strictly single-step point navigation)."""
        self.status_message = ""
        self._consecutive_move_count = 0
        parent = self.current_dir.parent
        if parent != self.current_dir and parent.exists():
            old_name = self.current_dir.name
            self.current_dir = parent.resolve()
            self.refresh_items()
            # Select previously active directory
            for idx, item in enumerate(self.current_items):
                if item.name == old_name:
                    self.selected_idx = idx
                    break
            if self.app:
                self.app.invalidate()

    def copy_selected_path(self) -> bool:
        """Copies the absolute path of the selected item (or current directory) to clipboard."""
        selected = self.get_selected_item()
        target_path = str(selected.resolve()) if selected else str(self.current_dir.resolve())
        success = copy_to_clipboard(target_path)
        if success:
            display_name = Path(target_path).name or target_path
            self.status_message = f"✔ Copied: {display_name}"
        else:
            self.status_message = "❌ Failed to copy path"
        if self.app:
            self.app.invalidate()
        return success

    def confirm_teleport(self) -> None:
        """Exits and sets target_cd so Kapsel teleports terminal directory."""
        selected = self.get_selected_item()
        if selected and selected.is_dir():
            self.target_cd = selected.resolve()
        else:
            self.target_cd = self.current_dir.resolve()
        if self.app:
            self.app.exit()

    def quit(self) -> None:
        """Exits without changing directory."""
        self.target_cd = None
        if self.app:
            self.app.exit()

    # --------------------------------------------------------------------------
    # Renderers
    # --------------------------------------------------------------------------

    def render_header(self) -> List[Tuple[str, str]]:
        """Renders top status bar."""
        term_width = shutil.get_terminal_size((80, 24)).columns
        item_count = len(self.current_items)
        selected_num = f"{self.selected_idx + 1}/{item_count}" if item_count else "0/0"
        path_str = f" 📁 {self.current_dir} "
        stat_str = f" [{selected_num} items] "
        padding = " " * max(0, term_width - len(path_str) - len(stat_str))
        return [
            ("class:fm.header_path", path_str),
            ("class:fm.header", padding),
            ("class:fm.header_stat", stat_str),
        ]

    def render_footer(self) -> List[Tuple[str, str]]:
        """Renders bottom shortcut navigation hints or status message."""
        if self.status_message:
            return [
                ("class:fm.footer", " "),
                ("class:fm.footer_copied", f" {self.status_message} "),
                ("class:fm.footer", " · "),
                ("class:fm.footer_key", "[Enter]"),
                ("class:fm.footer", " CD · "),
                ("class:fm.footer_key", "[c]"),
                ("class:fm.footer", " Copy path · "),
                ("class:fm.footer_key", "[q]"),
                ("class:fm.footer", " Quit "),
            ]
        return [
            ("class:fm.footer", " "),
            ("class:fm.footer_key", "[h/l]"),
            ("class:fm.footer", " Back/Open · "),
            ("class:fm.footer_key", "[j/k]"),
            ("class:fm.footer", " Select · "),
            ("class:fm.footer_key", "[Enter]"),
            ("class:fm.footer", " CD to here · "),
            ("class:fm.footer_key", "[c]"),
            ("class:fm.footer", " Copy path · "),
            ("class:fm.footer_key", "[q]"),
            ("class:fm.footer", " Quit "),
        ]

    def render_parent_col(self) -> List[Tuple[str, str]]:
        """Column 1: Parent directory preview."""
        term_height = max(10, shutil.get_terminal_size((80, 24)).lines - 4)
        result: List[Tuple[str, str]] = []

        if not self.parent_items:
            return [("class:fm.parent_file", " (No parent)\n")]

        curr_name = self.current_dir.name
        # Find index of current dir in parent
        curr_idx = 0
        for i, item in enumerate(self.parent_items):
            if item.name == curr_name:
                curr_idx = i
                break

        # Calculate scrolling window
        start = max(0, min(curr_idx - term_height // 2, len(self.parent_items) - term_height))
        visible_items = self.parent_items[start : start + term_height]

        for item in visible_items:
            is_curr = item.name == curr_name
            icon = "📁" if item.is_dir() else " "
            name = item.name[:22]
            if is_curr:
                result.append(("class:fm.parent_curr", f" > {icon} {name}\n"))
            elif item.is_dir():
                result.append(("class:fm.parent_dir", f"   {icon} {name}\n"))
            else:
                result.append(("class:fm.parent_file", f"     {name}\n"))

        return result

    def render_current_col(self) -> List[Tuple[str, str]]:
        """Column 2: Current directory list with cursor."""
        term_height = max(10, shutil.get_terminal_size((80, 24)).lines - 4)
        result: List[Tuple[str, str]] = []

        if not self.current_items:
            return [("class:fm.size", "   (Empty directory)\n")]

        # Calculate scrolling window centered around selected_idx
        start = max(0, min(self.selected_idx - term_height // 2, len(self.current_items) - term_height))
        visible_items = self.current_items[start : start + term_height]

        for i, item in enumerate(visible_items):
            actual_idx = start + i
            is_selected = (actual_idx == self.selected_idx)
            icon = get_file_icon(item)
            display_name = item.name

            # Format file size
            try:
                size_str = format_size(item.stat().st_size) if not item.is_dir() else "dir"
            except Exception:
                size_str = "-"

            # Padding
            truncated_name = display_name[:24]
            pad_len = max(1, 26 - len(truncated_name))
            pad = " " * pad_len

            if is_selected:
                style_prefix = "class:fm.item_selected_dir" if item.is_dir() else "class:fm.item_selected"
                result.append(("class:fm.item_cursor", " > "))
                result.append((style_prefix, f"{icon} {truncated_name}{pad}"))
                result.append((style_prefix, f"{size_str:>5}\n"))
            else:
                style_prefix = "class:fm.item_dir" if item.is_dir() else "class:fm.item_file"
                result.append((style_prefix, f"   {icon} {truncated_name}{pad}"))
                result.append(("class:fm.size", f"{size_str:>5}\n"))

        return result

    def render_preview_col(self) -> List[Tuple[str, str]]:
        """Column 3: Live preview of highlighted file or folder."""
        selected = self.get_selected_item()
        if not selected:
            return [("class:fm.size", " (No item selected)\n")]

        cache_key = f"{selected}_{selected.stat().st_mtime if selected.exists() else 0}"
        if cache_key in self.preview_cache:
            return self.preview_cache[cache_key]

        term_height = max(10, shutil.get_terminal_size((80, 24)).lines - 4)
        res: List[Tuple[str, str]] = []

        # 1. Directory Preview: Show child tree/list
        if selected.is_dir():
            res.append(("class:fm.preview_header", f" 📁 Directory: {selected.name}\n"))
            try:
                children = list(selected.iterdir())
                dirs = sum(1 for c in children if c.is_dir())
                files = len(children) - dirs
                res.append(("class:fm.preview_dir_head", f" Contains: {dirs} folders, {files} files\n\n"))
                for child in children[: term_height - 3]:
                    icon = get_file_icon(child)
                    res.append(("class:fm.preview_dir_item", f"   {icon} {child.name}\n"))
                if len(children) > term_height - 3:
                    res.append(("class:fm.size", f"   ... and {len(children) - (term_height - 3)} more items\n"))
            except PermissionError:
                res.append(("class:fm.size", "   [Permission Denied]\n"))
            except Exception as e:
                res.append(("class:fm.size", f"   [Error reading directory: {e}]\n"))

        # 2. File Preview
        else:
            try:
                size_bytes = selected.stat().st_size
                suffix = selected.suffix.lower()
                is_archive = suffix in ARCHIVE_EXTENSIONS
                is_image = suffix in IMAGE_EXTENSIONS

                if is_archive:
                    header_icon = "📦"
                elif is_image:
                    header_icon = "🖼️"
                else:
                    header_icon = "📄"

                res.append(("class:fm.preview_header", f" {header_icon} {selected.name} ({format_size(size_bytes)})\n"))

                # 2a. Image Preview via Chafa
                if is_image:
                    tool_chafa = shutil.which("chafa")
                    if not tool_chafa:
                        for candidate in [
                            Path(os.environ.get("USERPROFILE", Path.home())) / "scoop" / "shims" / "chafa.exe",
                            Path(os.environ.get("USERPROFILE", Path.home())) / ".kapsel" / "bin" / "chafa.exe",
                            Path(os.environ.get("WINDIR", "C:\\WINDOWS")) / "system32" / "chafa.exe",
                        ]:
                            if candidate.exists():
                                tool_chafa = str(candidate)
                                break

                    if tool_chafa:
                        preview_width = max(16, shutil.get_terminal_size((80, 24)).columns - 64)
                        preview_height = max(8, term_height - 2)
                        try:
                            cp = subprocess.run(
                                [tool_chafa, f"--size={preview_width}x{preview_height}", "--colors=full", str(selected)],
                                capture_output=True,
                                timeout=5,
                            )
                            if cp.returncode == 0 and cp.stdout:
                                ansi_out = cp.stdout.decode("utf-8", errors="replace")
                                img_tokens = list(to_formatted_text(ANSI(ansi_out)))
                                res.extend(img_tokens)
                                self.preview_cache[cache_key] = res
                                return res
                        except Exception:
                            pass

                    res.append(("class:fm.size", "\n [Image preview requires chafa]\n"))
                    res.append(("class:fm.preview_lineno", " Install via: kapsel install preview\n"))
                    self.preview_cache[cache_key] = res
                    return res

                # 2b. Archive Preview (zip, 7z, tar, etc.)
                if is_archive:
                    entries = _get_archive_entries(selected)
                    if entries is not None:
                        total_unpacked = sum(e[1] for e in entries if not e[2])
                        res.append(("class:fm.preview_dir_head", f" Contains: {len(entries)} items ({format_size(total_unpacked)} unpacked)\n\n"))
                        for entry_name, entry_size, is_dir in entries[: term_height - 4]:
                            icon = "📁" if is_dir else get_file_icon(Path(entry_name))
                            size_str = format_size(entry_size) if not is_dir else "dir"
                            display_name = entry_name[:36]
                            res.append(("class:fm.preview_dir_item", f"   {icon} {display_name}"))
                            res.append(("class:fm.size", f"  ({size_str})\n"))
                        if len(entries) > term_height - 4:
                            res.append(("class:fm.size", f"   ... and {len(entries) - (term_height - 4)} more items\n"))
                        self.preview_cache[cache_key] = res
                        return res

                # 2b. Standard File (Text or Binary)
                with open(selected, "rb") as f:
                    chunk = f.read(1024)
                    is_binary = b"\x00" in chunk

                if is_binary:
                    res.append(("class:fm.size", "\n [Binary file - preview not displayed]\n"))
                    hex_sample = " ".join(f"{b:02x}" for b in chunk[:32])
                    res.append(("class:fm.preview_lineno", f" Hex sample: {hex_sample}...\n"))
                else:
                    # Text preview
                    with open(selected, "r", encoding="utf-8", errors="replace") as f:
                        lines = [f.readline() for _ in range(term_height - 2)]
                    for idx, line in enumerate(lines, start=1):
                        cleaned = line.rstrip("\r\n")[:60]
                        res.append(("class:fm.preview_lineno", f" {idx:3d} │ "))
                        res.append(("class:fm.preview_text", f"{cleaned}\n"))
            except Exception as e:
                res.append(("class:fm.size", f" [Error loading preview: {e}]\n"))

        self.preview_cache[cache_key] = res
        return res

    def build_app(self) -> Application:
        """Builds prompt_toolkit Application with 3-column layout."""
        kb = KeyBindings()

        @kb.add("up", eager=True)
        @kb.add("k", eager=True)
        def _up(event):
            self.move_up()

        @kb.add("down", eager=True)
        @kb.add("j", eager=True)
        def _down(event):
            self.move_down()

        @kb.add("pageup", eager=True)
        @kb.add("K", eager=True)
        @kb.add("s-up", eager=True)
        @kb.add("c-u", eager=True)
        def _page_up(event):
            self.move_up(step=5)

        @kb.add("pagedown", eager=True)
        @kb.add("J", eager=True)
        @kb.add("s-down", eager=True)
        @kb.add("c-d", eager=True)
        def _page_down(event):
            self.move_down(step=5)

        @kb.add("right")
        @kb.add("l")
        def _right(event):
            self.enter_dir_or_open()

        @kb.add("left")
        @kb.add("h")
        def _left(event):
            self.ascend_to_parent()

        @kb.add("enter")
        def _enter(event):
            self.confirm_teleport()

        @kb.add("c")
        @kb.add("y")
        def _copy(event):
            self.copy_selected_path()

        @kb.add("q")
        @kb.add("escape")
        @kb.add("c-c")
        def _quit(event):
            self.quit()

        # Layout windows
        header_win = Window(FormattedTextControl(self.render_header), height=1)
        footer_win = Window(FormattedTextControl(self.render_footer), height=1)

        parent_win = Window(FormattedTextControl(self.render_parent_col), width=24)
        current_win = Window(FormattedTextControl(self.render_current_col), width=36)
        preview_win = Window(FormattedTextControl(self.render_preview_col))

        sep1 = Window(width=1, char="│", style="class:fm.border")
        sep2 = Window(width=1, char="│", style="class:fm.border")

        columns = VSplit([parent_win, sep1, current_win, sep2, preview_win])
        root_container = HSplit([header_win, columns, footer_win])

        self.app = Application(
            layout=Layout(root_container),
            key_bindings=kb,
            style=FM_STYLE,
            full_screen=True,
            mouse_support=False,
            output=get_safe_output(),
        )
        return self.app


def run_file_manager(initial_target: Optional[Path] = None) -> Optional[Path]:
    """
    Synchronously runs the interactive 3-column Miller Columns file manager.
    Returns the target directory to 'cd' into, or None if cancelled.
    """
    manager = FileManagerApp(initial_target)
    app = manager.build_app()
    try:
        app.run()
    except Exception:
        pass
    return manager.target_cd

