"""
Paginated Interactive TUI Viewer Container (viewer.py) for Kapsel Preview Plugin.
Provides a unified, cyber-modern document container with a clear "Page Concept":
1. PDF Documents:
   - Full multi-page navigation ([Right/Down/Space/n] next, [Left/Up/p] prev, [g] jump).
   - Dual Render Modes: Visual Image Mode (pdftoppm + chafa) & Text Mode (pdftotext).
   - Toggleable with [t] key; in-memory LRU page caching for instant flipping.
2. Text & Code Documents (up to 8,000+ lines):
   - Screen-based pagination: Page X / Y (Lines A-B of Total, %).
   - Smooth line ([j/k]) and half-page ([d/u]) scrolling, line number toggle ([l]), wrap toggle ([w]).
   - In-document search ([/]) with real-time match highlighting and [n]/[N] jump.
   - Syntax-colored rendering via Pygments / ANSI parser.
3. Tabular Data (CSV / TSV):
   - Paginated rows with pinned header row.

All comments and descriptions are in English.
"""

from collections import OrderedDict
import glob
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from typing import List, Optional, Tuple

from prompt_toolkit.application import Application
from prompt_toolkit.filters import Condition
from prompt_toolkit.formatted_text import ANSI, FormattedText, to_formatted_text
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import HSplit, Layout, VSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.output.color_depth import ColorDepth
from prompt_toolkit.styles import Style

try:
    from .fm import get_file_icon, format_size
except ImportError:
    try:
        from plugins.preview.fm import get_file_icon, format_size
    except ImportError:
        def get_file_icon(path: Path) -> str:
            return "📄"
        def format_size(size_bytes: int) -> str:
            return f"{size_bytes}B"


VIEWER_STYLE = Style.from_dict({
    "header": "bold #00f0ff bg:#181825",
    "header.title": "bold #f8fafc bg:#181825",
    "header.badge": "bold #10b981 bg:#1e293b",
    "header.stat": "dim #38bdf8 bg:#181825",
    "header.mode": "bold #a855f7 bg:#181825",
    "footer": "dim #94a3b8 bg:#181825",
    "footer.key": "bold #38bdf8 bg:#181825",
    "footer.prompt": "bold #f59e0b bg:#1e293b",
    "canvas": "#e2e8f0 bg:#0f172a",
    "lineno": "dim #475569",
    "lineno.active": "bold #38bdf8",
    "border": "dim #334155",
    "border.active": "bold #0891b2",
    "search.match": "bold #000000 bg:#facc15",
    "search.curr": "bold #000000 bg:#f97316",
    "table.header": "bold #00f0ff bg:#1e293b",
    "table.row_even": "#e2e8f0 bg:#0f172a",
    "table.row_odd": "#cbd5e1 bg:#131c31",
})


def _resolve_tool_executable(name: str) -> Optional[str]:
    """Locates an executable across standard PATH and Kapsel bin directories."""
    p = shutil.which(name)
    if p:
        return p
    is_win = sys.platform == "win32"
    exe_name = f"{name}.exe" if is_win else name
    user_home = Path(os.environ.get("USERPROFILE" if is_win else "HOME", Path.home()))
    candidates = [
        user_home / ".kapsel" / "bin" / exe_name,
        user_home / "scoop" / "shims" / exe_name,
        user_home / "scoop" / "apps" / name / "current" / exe_name,
        user_home / ".cargo" / "bin" / exe_name,
        user_home / ".local" / "bin" / exe_name,
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return None


def get_pdf_page_count(path: Path) -> int:
    """Detects the total number of pages in a PDF document."""
    pdfinfo_bin = _resolve_tool_executable("pdfinfo")
    if pdfinfo_bin:
        try:
            res = subprocess.run([pdfinfo_bin, str(path)], capture_output=True, timeout=3)
            if res.returncode == 0:
                out = res.stdout.decode("utf-8", errors="replace")
                m = re.search(r"Pages:\s+(\d+)", out)
                if m:
                    return max(1, int(m.group(1)))
        except Exception:
            pass

    # Fast pure-Python fallback: regex search for /Type /Pages /Count N
    try:
        raw = path.read_bytes()
        matches = re.findall(b"/Type\\s*/Pages.*?/Count\\s+(\\d+)", raw)
        if matches:
            counts = [int(c) for c in matches if int(c) > 0]
            if counts:
                return max(counts)
    except Exception:
        pass
    return 1


class ViewerApp:
    """
    Stateful full-screen paginated document viewer container.
    Supports PDF multi-page flipping with visual/text modes, image and archive
    rendering, and text/code/table scrolling with pagination and search.
    """

    def __init__(self, target_path: Path, initial_page: int = 1):
        self.path = target_path.resolve()
        self.suffix = self.path.suffix.lower()
        self.is_pdf = self.suffix == ".pdf"
        self.is_csv = self.suffix in (".csv", ".tsv")
        self.is_image = self.suffix in (
            ".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif", ".ico", ".bmp",
            ".tiff", ".avif", ".heic", ".jxl",
        )
        self.is_archive = self.suffix in (
            ".zip", ".tar", ".gz", ".tgz", ".bz2", ".tbz2", ".xz", ".txz",
            ".7z", ".rar", ".whl", ".jar", ".iso", ".apk", ".zst",
        )

        # Dimensions
        term_size = shutil.get_terminal_size((100, 30))
        self.term_cols = term_size.columns
        self.term_rows = term_size.lines

        # PDF Specific State
        self.pdf_total_pages = get_pdf_page_count(self.path) if self.is_pdf else 1
        self.current_page = max(1, min(initial_page, self.pdf_total_pages))
        self.pdf_mode: str = "visual"  # "visual" or "text"
        self.pdf_cache: OrderedDict[Tuple[int, str, int, int, int], List[Tuple[str, str]]] = OrderedDict()
        self._PDF_CACHE_MAX = 24
        self._cache_lock = threading.Lock()

        # Text / Code State
        self.lines: List[str] = []
        self.colored_lines: List[List[Tuple[str, str]]] = []
        self.total_lines: int = 0
        self.scroll_top: int = 0
        self.show_lineno: bool = True
        self.word_wrap: bool = False

        # Search & Interactive Input Mode
        self.input_mode: Optional[str] = None  # None, "search", or "goto"
        self.input_buffer: str = ""
        self.search_query: str = ""
        self.search_matches: List[int] = []  # Line numbers containing matches
        self.search_idx: int = -1

        # Application instance
        self.app: Optional[Application] = None

        self._load_content()

    def _load_content(self) -> None:
        """Loads file content and precomputes initial representation."""
        if self.is_pdf or self.is_image:
            return

        if self.is_archive:
            self._load_archive_listing()
            return

        try:
            # Read text with universal newline support
            text = self.path.read_text(encoding="utf-8", errors="replace")
            self.lines = text.splitlines()
        except Exception as e:
            self.lines = [f"Error loading file: {e}"]

        self.total_lines = len(self.lines)

        # Highlight code syntax if Pygments is available
        self._highlight_lines()

    def _load_archive_listing(self) -> None:
        """Loads an archive member listing instead of decoding archive bytes as text."""
        tool_7z = _resolve_tool_executable("7zz") or _resolve_tool_executable("7z")
        tool_tar = _resolve_tool_executable("tar")

        try:
            if tool_7z:
                result = subprocess.run(
                    [tool_7z, "l", "-sccUTF-8", "-xr!__MACOSX", str(self.path)],
                    capture_output=True,
                    timeout=8,
                )
            elif tool_tar and self.path.name.lower().endswith((
                ".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tbz2", ".tar.xz", ".txz",
            )):
                result = subprocess.run(
                    [tool_tar, "-tvf", str(self.path)], capture_output=True, timeout=8
                )
            else:
                self.lines = [
                    "Archive preview requires 7z or 7zz.",
                    "Install it with: kapsel install preview",
                ]
                self.total_lines = len(self.lines)
                self._highlight_lines()
                return

            output = result.stdout.decode("utf-8", errors="replace")
            if result.returncode == 0:
                self.lines = output.splitlines() or ["Archive is empty."]
            else:
                detail = result.stderr.decode("utf-8", errors="replace").strip()
                self.lines = ["Unable to list archive contents.", detail or output.strip() or "Unknown archive error."]
        except subprocess.TimeoutExpired:
            self.lines = ["Archive listing timed out after 8 seconds."]
        except Exception as exc:
            self.lines = [f"Unable to list archive contents: {exc}"]

        self.total_lines = len(self.lines)
        self._highlight_lines()

    def _cache_key(self, page_num: int, mode: str, cols: int, rows: int) -> Tuple[int, str, int, int, int]:
        """Returns a cache key that changes when the source file is replaced."""
        try:
            modified = self.path.stat().st_mtime_ns
        except OSError:
            modified = 0
        return (page_num, mode, cols, rows, modified)

    def _cache_get(self, key: Tuple[int, str, int, int, int]) -> Optional[List[Tuple[str, str]]]:
        """Returns a cached render and refreshes its LRU position."""
        with self._cache_lock:
            value = self.pdf_cache.get(key)
            if value is not None:
                self.pdf_cache.move_to_end(key)
            return value

    def _cache_put(self, key: Tuple[int, str, int, int, int], value: List[Tuple[str, str]]) -> None:
        """Stores a render while keeping the shared LRU cache bounded."""
        with self._cache_lock:
            self.pdf_cache[key] = value
            self.pdf_cache.move_to_end(key)
            while len(self.pdf_cache) > self._PDF_CACHE_MAX:
                self.pdf_cache.popitem(last=False)

    def _highlight_lines(self) -> None:
        """Formats and highlights lines of code using Pygments terminal formatter."""
        if not self.lines:
            self.colored_lines = []
            return

        try:
            from pygments import highlight
            from pygments.lexers import get_lexer_for_filename, TextLexer
            from pygments.formatters import Terminal256Formatter

            try:
                lexer = get_lexer_for_filename(str(self.path), stripnl=False)
            except Exception:
                lexer = TextLexer()

            content = "\n".join(self.lines)
            ansi_colored = highlight(content, lexer, Terminal256Formatter(style="monokai"))
            lines_ansi = ansi_colored.splitlines()

            self.colored_lines = []
            for l_ansi in lines_ansi:
                try:
                    toks = list(to_formatted_text(ANSI(l_ansi)))
                    self.colored_lines.append(toks)
                except Exception:
                    self.colored_lines.append([("", l_ansi)])
        except Exception:
            # Fallback to plain text tokens
            self.colored_lines = [[("", line)] for line in self.lines]

    def _render_pdf_page(
        self, page_num: int, cols: int, rows: int, mode: Optional[str] = None
    ) -> List[Tuple[str, str]]:
        """Renders a single PDF page in visual (pdftoppm+chafa) or text (pdftotext) mode."""
        render_mode = mode or self.pdf_mode
        cache_key = self._cache_key(page_num, render_mode, cols, rows)
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        pdftoppm_bin = _resolve_tool_executable("pdftoppm")
        chafa_bin = _resolve_tool_executable("chafa")
        pdftotext_bin = _resolve_tool_executable("pdftotext")

        # 1. Visual Image Mode
        if render_mode == "visual" and pdftoppm_bin and chafa_bin:
            with tempfile.TemporaryDirectory(prefix="kapsel_pdf_view_") as tmp_dir:
                out_prefix = Path(tmp_dir) / f"page_{page_num}"
                try:
                    conv_res = subprocess.run(
                        [pdftoppm_bin, "-f", str(page_num), "-l", str(page_num), "-singlefile", "-jpeg", "-jpegopt", "quality=85", str(self.path), str(out_prefix)],
                        capture_output=True,
                        timeout=8,
                    )
                    candidates = [
                        Path(candidate)
                        for candidate in glob.glob(str(out_prefix) + ".*")
                        if Path(candidate).is_file()
                    ]
                    image_file = candidates[0] if candidates else None
                    if conv_res.returncode == 0 and image_file:
                        target_h = max(10, rows)
                        target_w = max(20, cols)
                        chafa_res = subprocess.run(
                            [chafa_bin, f"--size={target_w}x{target_h}", "--colors=full", str(image_file)],
                            capture_output=True,
                            timeout=8,
                        )
                        if chafa_res.returncode == 0:
                            ansi_str = chafa_res.stdout.decode("utf-8", errors="replace")
                            tokens = list(to_formatted_text(ANSI(ansi_str)))
                            self._cache_put(cache_key, tokens)
                            return tokens
                except Exception:
                    pass

        # 2. Text Extraction Mode (or fallback when visual tools are absent)
        if pdftotext_bin:
            try:
                res = subprocess.run(
                    [pdftotext_bin, "-layout", "-f", str(page_num), "-l", str(page_num), str(self.path), "-"],
                    capture_output=True,
                    timeout=5,
                )
                if res.returncode == 0:
                    text_out = res.stdout.decode("utf-8", errors="replace")
                    if text_out.strip():
                        lines = text_out.splitlines()
                        out_tokens: List[Tuple[str, str]] = []
                        for idx, line in enumerate(lines, 1):
                            out_tokens.append(("class:lineno", f"{idx:3d} │ "))
                            out_tokens.append(("", line + "\n"))
                        self._cache_put(cache_key, out_tokens)
                        return out_tokens
                    return [("class:header.stat", f" [Page {page_num}: No extractable text] \n")]
            except Exception:
                pass

        err_tokens = [
            ("class:header.badge", " [Notice] "),
            ("", " pdftoppm or chafa is required for visual rendering. Press "),
            ("bold #00f0ff", "[t]"),
            ("", " to toggle text mode, or install via "),
            ("bold #10b981", "kapsel install poppler chafa"),
            ("", ".\n"),
        ]
        return err_tokens

    def _render_image_page(self, cols: int, rows: int) -> List[Tuple[str, str]]:
        """Renders an image directly through chafa inside the viewer body."""
        cache_key = self._cache_key(0, "image", cols, rows)
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        chafa_bin = _resolve_tool_executable("chafa")
        if not chafa_bin:
            return [
                ("class:header.badge", " [Notice] "),
                ("", " chafa is required to preview images. Install via "),
                ("bold #10b981", "kapsel install preview"),
                ("", ".\n"),
            ]

        try:
            target_h = max(10, rows)
            target_w = max(20, cols)
            result = subprocess.run(
                [chafa_bin, f"--size={target_w}x{target_h}", "--colors=full", str(self.path)],
                capture_output=True,
                timeout=8,
            )
            if result.returncode == 0:
                tokens = list(to_formatted_text(ANSI(result.stdout.decode("utf-8", errors="replace"))))
                self._cache_put(cache_key, tokens)
                return tokens
        except Exception:
            pass

        return [("class:header.badge", " [Notice] "), ("", " Unable to render this image.\n")]

    def _trigger_prefetch(self, cols: int, rows: int) -> None:
        """Warms the current PDF page's adjacent renders without blocking the UI."""
        if not self.is_pdf:
            return
        page_num = self.current_page
        render_mode = self.pdf_mode
        threading.Thread(
            target=self._prefetch_neighbors,
            args=(page_num, cols, rows, render_mode),
            daemon=True,
        ).start()

    def _prefetch_neighbors(self, page_num: int, cols: int, rows: int, mode: str) -> None:
        """Renders adjacent PDF pages into the shared LRU cache."""
        for delta in (1, -1):
            page = page_num + delta
            if not 1 <= page <= self.pdf_total_pages:
                continue
            key = self._cache_key(page, mode, cols, rows)
            if self._cache_get(key) is None:
                self._render_pdf_page(page, cols, rows, mode)

    def get_viewport_height(self) -> int:
        """Returns effective body line height available for content."""
        size = shutil.get_terminal_size((self.term_cols, self.term_rows))
        return max(5, size.lines - 4)

    def get_viewport_width(self) -> int:
        """Returns effective body width available for content."""
        size = shutil.get_terminal_size((self.term_cols, self.term_rows))
        return max(20, size.columns - 4)

    def get_header_tokens(self) -> List[Tuple[str, str]]:
        """Renders top header bar."""
        size = shutil.get_terminal_size((self.term_cols, self.term_rows))
        cols = size.columns
        icon = get_file_icon(self.path)
        name = self.path.name
        fsize = format_size(self.path.stat().st_size) if self.path.exists() else ""

        if self.is_pdf:
            type_tag = "[PDF]"
            page_info = f"Page {self.current_page}/{self.pdf_total_pages}"
            mode_tag = f"[{'Visual' if self.pdf_mode == 'visual' else 'Text'}]"
        elif self.is_image:
            type_tag = "[IMAGE]"
            page_info = "Visual preview"
            mode_tag = "[Chafa]"
        else:
            v_height = self.get_viewport_height()
            total_pages = max(1, math.ceil(self.total_lines / max(1, v_height)))
            curr_page = (self.scroll_top // v_height) + 1
            type_tag = f"[{self.suffix[1:].upper() if self.suffix else 'TEXT'}]"
            end_line = min(self.total_lines, self.scroll_top + v_height)
            pct = int((end_line / max(1, self.total_lines)) * 100) if self.total_lines > 0 else 100
            page_info = f"Page {curr_page}/{total_pages} ({self.scroll_top + 1}-{end_line}/{self.total_lines}, {pct}%)"
            mode_tag = f"[Wrap:{'ON' if self.word_wrap else 'OFF'}]"

        left_str = f" {icon} {name}  "
        center_str = f" {type_tag}  {page_info}  "
        right_str = f" {fsize}  {mode_tag} "

        spacing = max(1, cols - len(left_str) - len(center_str) - len(right_str))
        spacer1 = " " * (spacing // 2)
        spacer2 = " " * (spacing - len(spacer1))

        return [
            ("class:header.title", left_str),
            ("class:header", spacer1),
            ("class:header.badge", center_str),
            ("class:header", spacer2),
            ("class:header.stat", right_str),
        ]

    def get_footer_tokens(self) -> List[Tuple[str, str]]:
        """Renders bottom navigation cheat sheet or interactive search/goto bar."""
        if self.input_mode == "search":
            return [
                ("class:footer.prompt", " Search [/]: "),
                ("bold #ffffff bg:#1e293b", f" {self.input_buffer} "),
                ("dim #94a3b8 bg:#181825", "  [Enter] Confirm  [Esc] Cancel"),
            ]
        elif self.input_mode == "goto":
            prompt_label = " Goto Page (1-" + str(self.pdf_total_pages) + "): " if self.is_pdf else " Goto Line (1-" + str(self.total_lines) + "): "
            return [
                ("class:footer.prompt", prompt_label),
                ("bold #ffffff bg:#1e293b", f" {self.input_buffer} "),
                ("dim #94a3b8 bg:#181825", "  [Enter] Jump  [Esc] Cancel"),
            ]

        if self.is_image:
            return [
                ("class:footer.key", " [q/Esc]"),
                ("class:footer", " Quit "),
            ]

        # Standard Navigation Footer
        hints = [
            ("class:footer.key", " [q]"), ("class:footer", " Quit "),
            ("class:footer.key", " [←/→, Space]"), ("class:footer", " Page "),
            ("class:footer.key", " [↑/↓, j/k]"), ("class:footer", " Scroll "),
        ]
        if self.is_pdf:
            hints.extend([
                ("class:footer.key", " [t]"), ("class:footer", " Visual/Text "),
                ("class:footer.key", " [g]"), ("class:footer", " PageJump "),
            ])
        else:
            hints.extend([
                ("class:footer.key", " [/]"), ("class:footer", " Search "),
                ("class:footer.key", " [n/N]"), ("class:footer", " NextMatch "),
                ("class:footer.key", " [g]"), ("class:footer", " LineJump "),
                ("class:footer.key", " [l]"), ("class:footer", " LineNo "),
                ("class:footer.key", " [w]"), ("class:footer", " Wrap "),
            ])

        return hints

    def get_body_tokens(self) -> List[Tuple[str, str]]:
        """Renders viewport body according to active file type and page position."""
        size = shutil.get_terminal_size((self.term_cols, self.term_rows))
        cols = size.columns
        rows = self.get_viewport_height()

        # 1. PDF Mode Rendering
        if self.is_pdf:
            return self._render_pdf_page(self.current_page, cols, rows)

        # 2. Image Mode Rendering
        if self.is_image:
            return self._render_image_page(cols, rows)

        # 3. Text / Code / Archive Document Rendering
        tokens: List[Tuple[str, str]] = []
        line_num_width = len(str(self.total_lines)) if self.total_lines > 0 else 3
        visible_lines = self.colored_lines[self.scroll_top : self.scroll_top + rows]

        for i, line_toks in enumerate(visible_lines):
            line_idx = self.scroll_top + i + 1

            # Line number margin
            if self.show_lineno:
                is_curr = line_idx in self.search_matches if self.search_matches else False
                no_style = "class:lineno.active" if is_curr else "class:lineno"
                tokens.append((no_style, f"{line_idx:>{line_num_width}} │ "))

            # Highlight search matches if active
            if self.search_query and any(self.search_query.lower() in text.lower() for (_, text) in line_toks):
                for style, text in line_toks:
                    if self.search_query.lower() in text.lower():
                        parts = re.split(f"({re.escape(self.search_query)})", text, flags=re.IGNORECASE)
                        for p in parts:
                            if p.lower() == self.search_query.lower():
                                tokens.append(("class:search.match", p))
                            else:
                                tokens.append((style, p))
                    else:
                        tokens.append((style, text))
            else:
                tokens.extend(line_toks)

            tokens.append(("", "\n"))

        # Pad remaining lines if document is shorter than viewport
        if len(visible_lines) < rows:
            for _ in range(rows - len(visible_lines)):
                if self.show_lineno:
                    tokens.append(("class:lineno", " " * line_num_width + " │\n"))
                else:
                    tokens.append(("", "\n"))

        return tokens


def run_preview_viewer(target_path: Path, initial_page: int = 1) -> int:
    """
    Launches the interactive paginated TUI viewer container for a target file.
    Runs inside the alternate terminal buffer with instantaneous cleanup upon exit.
    """
    if not target_path.exists() or target_path.is_dir():
        return 1

    viewer = ViewerApp(target_path, initial_page=initial_page)
    kb = KeyBindings()

    is_normal = Condition(lambda: viewer.input_mode is None)
    is_input = Condition(lambda: viewer.input_mode is not None)

    def _prefetch_current_pdf() -> None:
        if viewer.is_pdf:
            size = shutil.get_terminal_size((viewer.term_cols, viewer.term_rows))
            viewer._trigger_prefetch(size.columns, viewer.get_viewport_height())

    # --------------------------------------------------------------------------
    # Normal Mode Key Bindings
    # --------------------------------------------------------------------------
    @kb.add("q", filter=is_normal)
    @kb.add("escape", filter=is_normal)
    def _quit(event):
        event.app.exit()

    # PDF & Text Page Flipping (Forward)
    @kb.add("right", filter=is_normal)
    @kb.add("pagedown", filter=is_normal)
    @kb.add("space", filter=is_normal)
    def _next_page(event):
        if viewer.is_pdf:
            if viewer.current_page < viewer.pdf_total_pages:
                viewer.current_page += 1
            _prefetch_current_pdf()
        else:
            v_height = viewer.get_viewport_height()
            viewer.scroll_top = min(max(0, viewer.total_lines - v_height), viewer.scroll_top + v_height)

    # PDF & Text Page Flipping (Backward)
    @kb.add("left", filter=is_normal)
    @kb.add("pageup", filter=is_normal)
    def _prev_page(event):
        if viewer.is_pdf:
            if viewer.current_page > 1:
                viewer.current_page -= 1
            _prefetch_current_pdf()
        else:
            v_height = viewer.get_viewport_height()
            viewer.scroll_top = max(0, viewer.scroll_top - v_height)

    # Line Scrolling (Down)
    @kb.add("down", filter=is_normal)
    @kb.add("j", filter=is_normal)
    def _scroll_down(event):
        if viewer.is_pdf:
            if viewer.current_page < viewer.pdf_total_pages:
                viewer.current_page += 1
            _prefetch_current_pdf()
        else:
            v_height = viewer.get_viewport_height()
            viewer.scroll_top = min(max(0, viewer.total_lines - v_height), viewer.scroll_top + 1)

    # Line Scrolling (Up)
    @kb.add("up", filter=is_normal)
    @kb.add("k", filter=is_normal)
    def _scroll_up(event):
        if viewer.is_pdf:
            if viewer.current_page > 1:
                viewer.current_page -= 1
            _prefetch_current_pdf()
        else:
            viewer.scroll_top = max(0, viewer.scroll_top - 1)

    # Half Page Scroll (Down / Up)
    @kb.add("d", filter=is_normal)
    def _half_down(event):
        if not viewer.is_pdf:
            v_height = viewer.get_viewport_height()
            viewer.scroll_top = min(max(0, viewer.total_lines - v_height), viewer.scroll_top + v_height // 2)

    @kb.add("u", filter=is_normal)
    def _half_up(event):
        if not viewer.is_pdf:
            v_height = viewer.get_viewport_height()
            viewer.scroll_top = max(0, viewer.scroll_top - v_height // 2)

    # First / Last Page (Home / End)
    @kb.add("home", filter=is_normal)
    def _home(event):
        if viewer.is_pdf:
            viewer.current_page = 1
            _prefetch_current_pdf()
        else:
            viewer.scroll_top = 0

    @kb.add("end", filter=is_normal)
    @kb.add("G", filter=is_normal)
    def _end(event):
        if viewer.is_pdf:
            viewer.current_page = viewer.pdf_total_pages
            _prefetch_current_pdf()
        else:
            v_height = viewer.get_viewport_height()
            viewer.scroll_top = max(0, viewer.total_lines - v_height)

    # Toggle Visual / Text Mode for PDF
    @kb.add("t", filter=is_normal)
    def _toggle_mode(event):
        if viewer.is_pdf:
            viewer.pdf_mode = "text" if viewer.pdf_mode == "visual" else "visual"
            _prefetch_current_pdf()

    # Toggle Line Numbers
    @kb.add("l", filter=is_normal)
    def _toggle_lineno(event):
        viewer.show_lineno = not viewer.show_lineno

    # Toggle Word Wrap
    @kb.add("w", filter=is_normal)
    def _toggle_wrap(event):
        viewer.word_wrap = not viewer.word_wrap

    # Open Goto Input
    @kb.add("g", filter=is_normal)
    def _open_goto(event):
        viewer.input_mode = "goto"
        viewer.input_buffer = ""

    # Open Search Input
    @kb.add("/", filter=is_normal)
    def _open_search(event):
        if not viewer.is_pdf:
            viewer.input_mode = "search"
            viewer.input_buffer = ""

    # Next / Previous Search Match
    @kb.add("n", filter=is_normal)
    def _next_match(event):
        if viewer.search_matches:
            viewer.search_idx = (viewer.search_idx + 1) % len(viewer.search_matches)
            target_line = viewer.search_matches[viewer.search_idx]
            viewer.scroll_top = max(0, target_line - 2)

    @kb.add("N", filter=is_normal)
    def _prev_match(event):
        if viewer.search_matches:
            viewer.search_idx = (viewer.search_idx - 1) % len(viewer.search_matches)
            target_line = viewer.search_matches[viewer.search_idx]
            viewer.scroll_top = max(0, target_line - 2)

    # --------------------------------------------------------------------------
    # Interactive Input Mode (Search / Goto) Key Bindings
    # --------------------------------------------------------------------------
    @kb.add("escape", filter=is_input)
    def _cancel_input(event):
        viewer.input_mode = None
        viewer.input_buffer = ""

    @kb.add("backspace", filter=is_input)
    def _backspace_input(event):
        viewer.input_buffer = viewer.input_buffer[:-1]

    @kb.add("enter", filter=is_input)
    def _submit_input(event):
        val = viewer.input_buffer.strip()
        if viewer.input_mode == "goto":
            if val.isdigit():
                num = int(val)
                if viewer.is_pdf:
                    viewer.current_page = max(1, min(viewer.pdf_total_pages, num))
                    _prefetch_current_pdf()
                else:
                    v_height = viewer.get_viewport_height()
                    viewer.scroll_top = max(0, min(viewer.total_lines - v_height, num - 1))
        elif viewer.input_mode == "search":
            viewer.search_query = val
            if val:
                matches = []
                for idx, line in enumerate(viewer.lines):
                    if val.lower() in line.lower():
                        matches.append(idx + 1)
                viewer.search_matches = matches
                if matches:
                    viewer.search_idx = 0
                    viewer.scroll_top = max(0, matches[0] - 2)
            else:
                viewer.search_matches = []
                viewer.search_idx = -1

        viewer.input_mode = None
        viewer.input_buffer = ""

    @kb.add("<any>", filter=is_input)
    def _type_input(event):
        viewer.input_buffer += event.data

    # --------------------------------------------------------------------------
    # Layout Composition
    # --------------------------------------------------------------------------
    header_win = Window(content=FormattedTextControl(viewer.get_header_tokens), height=1)
    body_win = Window(
        content=FormattedTextControl(viewer.get_body_tokens),
        wrap_lines=Condition(lambda: viewer.word_wrap),
    )
    footer_win = Window(content=FormattedTextControl(viewer.get_footer_tokens), height=1)

    layout = Layout(HSplit([header_win, body_win, footer_win]))
    app = Application(
        layout=layout,
        key_bindings=kb,
        style=VIEWER_STYLE,
        color_depth=ColorDepth.DEPTH_24_BIT,
        full_screen=True,
    )
    viewer.app = app

    try:
        app.run()
        return 0
    except Exception:
        return 1
