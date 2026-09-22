"""
Preview (Smart Terminal Preview Dispatcher) Plugin for Kapsel.
Maps 10 major file categories directly to industry-standard CLI power tools:
1. Code & Scripts       -> bat
2. Markdown Documents   -> glow
3. Structured Data JSON -> jq
4. Tabular Data CSV/TSV -> xsv
5. Folders & Directory  -> eza / tree
6. Archives (zip, tar)  -> 7z / tar
7. Images               -> chafa
8. PDF Documents        -> pdftoppm + chafa
9. Media Audio/Video    -> mediainfo / ffprobe
10. Unknown Binaries    -> xxd / hexdump

No fallbacks: if the tool is not installed, cleanly outputs an error and installation tip.
All comments and descriptions are in English.
"""

from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Dict, List, Optional, Tuple

from rich.console import Console

from kapsel.core.plugin.base import KapselPlugin, PluginManifest
from kapsel.core.plugin.context import PluginContext
from kapsel.core.plugin.hooks import HookType
from kapsel.storage.config import get_kapsel_dir

try:
    from .fm import run_file_manager
except ImportError:
    from plugins.preview.fm import run_file_manager


try:
    from kapsel.ui.banner import ensure_utf8_io
    ensure_utf8_io()
except Exception:
    pass


def _resolve_tool_executable(name: str) -> Optional[str]:
    """
    Locates an executable across PATH, ~/.kapsel/bin, Scoop, WinGet, Cargo, and Unix paths.
    """
    # 1. System PATH
    p = shutil.which(name)
    if p:
        return p

    is_win = sys.platform == "win32"
    exe_name = f"{name}.exe" if is_win else name

    # 2. Local Kapsel bin directory (~/.kapsel/bin)
    local_bin = get_kapsel_dir() / "bin" / exe_name
    if local_bin.exists():
        return str(local_bin)

    user_home = Path(os.environ.get("USERPROFILE" if is_win else "HOME", Path.home()))

    # 3. Windows-specific package paths
    if is_win:
        candidates = [
            user_home / "scoop" / "shims" / exe_name,
            user_home / "scoop" / "apps" / name / "current" / exe_name,
            user_home / "AppData" / "Local" / "Microsoft" / "WinGet" / "Links" / exe_name,
            user_home / ".cargo" / "bin" / exe_name,
            user_home / ".local" / "bin" / exe_name,
        ]
        for candidate in candidates:
            if candidate.exists():
                return str(candidate)
    else:
        # 4. Unix-specific paths
        unix_candidates = [
            Path("/opt/homebrew/bin") / exe_name,
            Path("/usr/local/bin") / exe_name,
            Path("/usr/bin") / exe_name,
            user_home / ".cargo" / "bin" / exe_name,
            user_home / ".local" / "bin" / exe_name,
        ]
        for candidate in unix_candidates:
            if candidate.exists():
                return str(candidate)

    return None


class PreviewPlugin(KapselPlugin):
    """
    Kapsel Preview Plugin: Universal smart CLI preview dispatcher.
    Maps file types directly to specialized CLI tools (bat, glow, jq, xsv, eza, 7z, chafa, pdftoppm).
    """

    manifest = PluginManifest(
        id="preview",
        name="Preview",
        version="0.2.6",
        description="Smart terminal preview dispatcher inspired by Yazi's toolchain (bat, glow, jq, xsv, eza, 7z/7zz, chafa, pdftoppm, ffmpeg, magick, resvg), plus native 3-column Miller Columns file manager (fm).",
        author="Kapsel Team",
        homepage="https://github.com/MrEiu/plugins/tree/master/preview",
        min_kapsel_version="0.1.0",
        tags=["preview", "cat", "view", "fm", "file-manager", "miller-columns", "bat", "glow", "xsv", "eza", "chafa", "7z", "ffmpeg", "magick", "resvg", "pdftoppm", "mediainfo", "xxd"],
    )

    def __init__(self) -> None:
        super().__init__()
        self.context: Optional[PluginContext] = None

    def on_load(self, context: PluginContext) -> None:
        self.context = context

        # 1. Pre-execution filter: intercepts 'prev <target>', 'fm <target>', etc.
        context.register_hook(HookType.FILTER_COMMAND, self.filter_command)

        # 2. Dynamic autocompletion for files and directories
        context.register_hook(HookType.PROVIDE_COMPLETIONS, self.provide_completions)

        # 3. Register functional commands under kps namespace
        context.register_kps_command(
            name="preview",
            handler=self.handle_preview,
            help_text="Preview file or directory using dedicated industry-standard CLI tools",
            usage="kps preview [options] <path>",
            scope="feature",
        )
        context.register_kps_command(
            name="prev",
            handler=self.handle_preview,
            help_text="Alias for 'kps preview'",
            usage="kps prev [options] <path>",
            scope="feature",
        )
        context.register_kps_command(
            name="prew",
            handler=self.handle_preview,
            help_text="Alias for 'kps preview'",
            usage="kps prew [options] <path>",
            scope="feature",
        )
        context.register_kps_command(
            name="fm",
            handler=self.handle_fm,
            help_text="Interactive 3-column Miller Columns file manager",
            usage="kps fm [path]",
            scope="feature",
        )

    def handle_fm(self, args: List[str], console: Optional[Console] = None) -> int:
        """Handler for 'kps fm [path]'."""
        target = Path(args[0]).expanduser() if args else None
        target_cd = run_file_manager(target)
        if target_cd and console:
            console.print(f"[bold #10b981]⚡ Selected directory:[/] [white]{target_cd}[/]")
        return 0

    def filter_command(self, raw_command: str) -> Tuple[bool, str]:
        """
        Intercepts:
        1. 'fm [path]' or 'kps fm [path]' -> interactive 3-column Miller Columns directory mode
        2. 'prev <target>' / 'preview <target>' / 'prew <target>' -> CLI preview dispatcher
        """
        stripped = raw_command.strip()
        if not stripped:
            return False, raw_command

        tokens = stripped.split()
        prefix = tokens[0].lower()

        # 1. Interactive 3-column Miller Columns directory mode: 'fm [path]'
        if prefix == "fm":
            args = tokens[1:]
            target = Path(args[0]).expanduser() if args else None
            target_cd = run_file_manager(target)
            if target_cd:
                return True, f'cd "{target_cd}"'
            return True, ""

        # 2. Command 'kps fm [path]' or 'kps preview fm [path]'
        if stripped.lower().startswith("kps fm"):
            sub_tokens = stripped.split()[2:]
            target = Path(sub_tokens[0]).expanduser() if sub_tokens else None
            target_cd = run_file_manager(target)
            if target_cd:
                return True, f'cd "{target_cd}"'
            return True, ""

        if stripped.lower().startswith("kps preview fm"):
            sub_tokens = stripped.split()[3:]
            target = Path(sub_tokens[0]).expanduser() if sub_tokens else None
            target_cd = run_file_manager(target)
            if target_cd:
                return True, f'cd "{target_cd}"'
            return True, ""

        if prefix not in ("prev", "preview", "prew"):
            return False, raw_command

        args = tokens[1:]
        # Support 'prev -i [path]'
        if args and args[0] in ("-i", "--interactive"):
            target = Path(args[1]).expanduser() if len(args) > 1 else None
            target_cd = run_file_manager(target)
            if target_cd:
                return True, f'cd "{target_cd}"'
            return True, ""

        con = Console(legacy_windows=False)
        try:
            self.handle_preview(args, con)
        except Exception as e:
            con.print(f"[bold #f43f5e]Preview error:[/] {e}")
        return True, ""

    def provide_completions(self, text_before_cursor: str) -> List[dict]:
        """
        Provides file and directory path autocompletion when typing 'fm ', 'prev ' or 'kps preview '.
        """
        stripped = text_before_cursor.lstrip()
        matched_prefix = None
        for p in ("kps preview fm ", "kps preview ", "preview ", "prev ", "prew ", "fm "):
            if stripped.startswith(p):
                matched_prefix = p
                break

        if not matched_prefix:
            return []

        remainder = stripped[len(matched_prefix):]
        if remainder.startswith("-"):
            # Option suggestions
            return [
                {"text": "-l", "display": "-l, --lines <n>", "display_meta": "Max lines", "start_position": -len(remainder)},
                {"text": "-a", "display": "-a, --all", "display_meta": "Full output", "start_position": -len(remainder)},
            ]

        # File and directory completions based on current path
        query_path_str = remainder.strip()
        try:
            if not query_path_str:
                search_dir = Path.cwd()
                prefix_part = ""
            else:
                p = Path(query_path_str)
                if query_path_str.endswith(("/", "\\")):
                    search_dir = p if p.is_dir() else Path.cwd()
                    prefix_part = ""
                else:
                    search_dir = p.parent if p.parent.is_dir() else Path.cwd()
                    prefix_part = p.name

            candidates = []
            if search_dir.is_dir():
                for item in search_dir.iterdir():
                    if prefix_part and not item.name.lower().startswith(prefix_part.lower()):
                        continue
                    display_name = item.name + ("/" if item.is_dir() else "")
                    candidates.append({
                        "text": str(item),
                        "display": display_name,
                        "display_meta": "📁 dir" if item.is_dir() else "📄 file",
                        "start_position": -len(prefix_part) if prefix_part else 0,
                    })
            return candidates[:25]
        except Exception:
            return []

    def handle_preview(self, args: List[str], console: Optional[Console] = None) -> int:
        """Main dispatcher for preview requests."""
        con = console or Console(legacy_windows=False)

        if not args or args[0] in ("-h", "--help", "help"):
            self._render_help(con)
            return 0

        # Direct fm subcommand
        if args and args[0] == "fm":
            target = Path(args[1]).expanduser() if len(args) > 1 else None
            target_cd = run_file_manager(target)
            if target_cd:
                con.print(f"[bold #10b981]⚡ Selected directory:[/] [white]{target_cd}[/]")
            return 0

        target_str: Optional[str] = None
        lines_limit: Optional[int] = None
        page_num: int = 1
        force_cli: bool = False
        idx = 0

        while idx < len(args):
            arg = args[idx]
            if arg in ("-l", "--lines") and idx + 1 < len(args):
                try:
                    lines_limit = int(args[idx + 1])
                except ValueError:
                    pass
                idx += 2
            elif arg in ("-p", "--page") and idx + 1 < len(args):
                try:
                    page_num = max(1, int(args[idx + 1]))
                except ValueError:
                    pass
                idx += 2
            elif arg in ("-a", "--all"):
                lines_limit = 0
                idx += 1
            elif arg in ("--cli", "--raw"):
                force_cli = True
                idx += 1
            elif not arg.startswith("-") and target_str is None:
                target_str = arg
                idx += 1
            else:
                idx += 1

        if not target_str:
            con.print("[bold #f43f5e]Error:[/] Please specify a file or directory path to preview.")
            con.print("[dim]Usage: prev <path> [-p <page>] [-l <lines>] [--cli][/]\n")
            return 1

        target_path = Path(target_str).expanduser()
        if not target_path.exists():
            con.print(f"[bold #f43f5e]Error:[/] Path '[white]{target_str}[/]' does not exist.")
            return 1

        # 1. Directory -> opens native Miller Columns File Manager (fm)
        if target_path.is_dir():
            target_cd = run_file_manager(target_path)
            if target_cd:
                con.print(f"[bold #10b981]⚡ Selected directory:[/] [white]{target_cd}[/]")
            return 0

        # 2. Files -> dispatch directly to dedicated native CLI tools
        return self.dispatch_preview(target_path, con, lines_limit=lines_limit, page_num=page_num)

    def dispatch_preview(
        self,
        path: Path,
        con: Console,
        lines_limit: Optional[int] = None,
        page_num: int = 1,
    ) -> int:
        """
        Inspects path type and extension, dispatching directly to the dedicated CLI tool.
        If the tool is missing, displays an error message without fallback.
        """
        # 1. Directory -> eza / tree
        if path.is_dir():
            return self._exec_directory(path, con)

        suffix = path.suffix.lower()

        # 2. Markdown -> glow
        if suffix in (".md", ".markdown", ".mdown", ".mkd", ".rst"):
            return self._exec_markdown(path, con)

        # 3. Tabular Data (CSV / TSV) -> xsv
        if suffix in (".csv", ".tsv"):
            return self._exec_csv(path, con)

        # 4. Structured Data (JSON) -> jq (Yazi-style: jq --tab with code fallback)
        if suffix in (".json", ".json5", ".jsonl"):
            return self._exec_json(path, con, lines_limit)

        # 5. Archives -> 7zz / 7z / tar (Yazi-style: UTF-8, ignore macOS metadata, piped tarball)
        if suffix in (".zip", ".tar", ".gz", ".tgz", ".bz2", ".tbz2", ".xz", ".txz", ".7z", ".rar", ".whl", ".jar", ".iso", ".apk", ".zst"):
            return self._exec_archive(path, con)

        # 6. Fonts -> magick + chafa (Yazi-style font specimen rendering)
        if suffix in (".ttf", ".otf", ".woff", ".woff2", ".eot", ".ttc"):
            return self._exec_font(path, con)

        # 7. Images & Vectors (SVG) -> resvg / magick / chafa
        if suffix in (".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif", ".ico", ".bmp", ".tiff", ".avif", ".heic", ".jxl"):
            return self._exec_image(path, con)

        # 8. PDF Documents -> pdftoppm -> chafa (Yazi-style page rendering)
        if suffix == ".pdf":
            return self._exec_pdf(path, con, page=page_num)

        # 9. Media Audio/Video -> ffmpeg keyframe thumbnail + mediainfo / ffprobe metadata
        if suffix in (".mp4", ".mkv", ".avi", ".mov", ".flv", ".wmv", ".webm", ".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac"):
            return self._exec_media(path, con)

        # 10. Binary / Executable -> xxd / hexdump
        if suffix in (".exe", ".dll", ".so", ".dylib", ".bin", ".dat", ".class", ".o", ".pyc") or self._is_binary_file(path):
            return self._exec_binary(path, con)

        # 11. Code & Plaintext -> bat (Default)
        return self._exec_code(path, con, lines_limit)

    def _is_binary_file(self, path: Path) -> bool:
        """Checks if a file contains null bytes within the first 1KB."""
        try:
            with open(path, "rb") as f:
                chunk = f.read(1024)
                return b"\x00" in chunk
        except Exception:
            return False

    # --------------------------------------------------------------------------
    # Tool Execution Handlers (Aligned with Yazi's Previewer Architecture)
    # --------------------------------------------------------------------------

    def _report_missing_tool(self, tool_name: str, category: str, con: Console) -> int:
        """Prints a clean, actionable error message when the required CLI tool is missing."""
        con.print(f"[bold #f43f5e]preview:[/] '[bold white]{tool_name}[/]' is not installed for {category}.")
        con.print(f"[dim]Tip: Install '{tool_name}' via your package manager (e.g. 'scoop install {tool_name}', 'brew install {tool_name}') or run 'kps install preview'.[/]\n")
        return 1

    def _exec_directory(self, path: Path, con: Console) -> int:
        """Directory preview via eza or tree."""
        tool = _resolve_tool_executable("eza")
        if tool:
            return subprocess.run([tool, "--tree", "--level=3", "--icons", str(path)]).returncode

        tree_tool = _resolve_tool_executable("tree")
        if tree_tool:
            return subprocess.run([tree_tool, "-L", "3", str(path)]).returncode

        return self._report_missing_tool("eza (or tree)", "previewing directories", con)

    def _exec_markdown(self, path: Path, con: Console) -> int:
        """Markdown preview via glow."""
        tool = _resolve_tool_executable("glow")
        if tool:
            return subprocess.run([tool, "--style=auto", str(path)]).returncode
        return self._report_missing_tool("glow", "previewing markdown files", con)

    def _exec_csv(self, path: Path, con: Console) -> int:
        """Tabular data preview via xsv."""
        tool = _resolve_tool_executable("xsv")
        if tool:
            return subprocess.run([tool, "table", str(path)]).returncode
        return self._report_missing_tool("xsv", "previewing CSV/TSV tables", con)

    def _exec_json(self, path: Path, con: Console, lines_limit: Optional[int] = None) -> int:
        """
        JSON structured data preview via jq.
        Yazi pattern: runs 'jq -b -C --tab . <path>'. If jq is missing or errors,
        seamlessly falls back to syntax-highlighted code preview (bat).
        """
        tool = _resolve_tool_executable("jq")
        if tool:
            res = subprocess.run([tool, "-b", "-C", "--tab", ".", str(path)])
            if res.returncode == 0:
                return 0
        # Fallback to code highlighter (bat), identical to Yazi's json.lua fallback
        return self._exec_code(path, con, lines_limit)

    def _exec_archive(self, path: Path, con: Console) -> int:
        """
        Archive preview via 7zz / 7z or tar.
        Yazi pattern:
        1. Uses 7zz or 7z with flags: -sccUTF-8 -xr!__MACOSX
        2. For compressed tarballs (.tar.gz, .tgz, .tar.xz, etc.), pipes extraction into tar listing:
           '7z x -so <path> | 7z l -ttar -sccUTF-8 -xr!__MACOSX -si'
        3. Fallback: tar -tvf
        """
        tool_7z = _resolve_tool_executable("7zz") or _resolve_tool_executable("7z")
        name_lower = path.name.lower()
        is_compressed_tar = any(
            name_lower.endswith(ext)
            for ext in (".tar.gz", ".tgz", ".tar.xz", ".txz", ".tar.bz2", ".tbz2", ".tar.zst")
        )

        if tool_7z:
            if is_compressed_tar:
                try:
                    p1 = subprocess.Popen(
                        [tool_7z, "x", "-so", str(path)],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL,
                    )
                    p2 = subprocess.Popen(
                        [tool_7z, "l", "-ttar", "-sccUTF-8", "-xr!__MACOSX", "-si"],
                        stdin=p1.stdout,
                        stdout=None,
                    )
                    if p1.stdout:
                        p1.stdout.close()
                    p2.communicate()
                    return p2.returncode
                except Exception:
                    pass

            return subprocess.run([tool_7z, "l", "-sccUTF-8", "-xr!__MACOSX", str(path)]).returncode

        tool_tar = _resolve_tool_executable("tar")
        if tool_tar:
            return subprocess.run([tool_tar, "-tvf", str(path)]).returncode

        return self._report_missing_tool("7z (or tar)", "inspecting archives", con)

    def _exec_font(self, path: Path, con: Console) -> int:
        """
        Font specimen preview via ImageMagick (magick) + chafa.
        Yazi pattern: Renders alphabet and numeric specimen into a temporary image using
        'magick -size 800x560 -gravity center -font <path> -pointsize 64 xc:white -fill black -annotate +0+0 ...'
        then displays it in the terminal via chafa.
        """
        tool_magick = _resolve_tool_executable("magick")
        tool_chafa = _resolve_tool_executable("chafa")

        if tool_magick and tool_chafa:
            specimen_text = "ABCDEFGHIJKLM\nNOPQRSTUVWXYZ\nabcdefghijklm\nnopqrstuvwxyz\n1234567890\n!$&*()[]{}"
            with tempfile.TemporaryDirectory(prefix="kapsel_font_") as tmp_dir:
                tmp_img = Path(tmp_dir) / "font_specimen.jpg"
                res = subprocess.run([
                    tool_magick,
                    "-size", "800x560",
                    "-gravity", "center",
                    "-font", str(path),
                    "-pointsize", "48",
                    "xc:white",
                    "-fill", "black",
                    "-annotate", "+0+0", specimen_text,
                    f"JPG:{tmp_img}",
                ], capture_output=True)
                if res.returncode == 0 and tmp_img.exists():
                    con.print(f"[dim italic]🔤 Font Specimen: {path.name}[/]")
                    return subprocess.run([tool_chafa, str(tmp_img)]).returncode

        return self._report_missing_tool("magick and chafa", "visually previewing font files in terminal", con)

    def _exec_image(self, path: Path, con: Console) -> int:
        """
        Image & Vector preview via resvg / magick / chafa Sixel output.
        SVG files are rasterized first; all image output uses the native Sixel
        graphics protocol instead of character-art rendering.
        """
        tool_chafa = _resolve_tool_executable("chafa")
        if not tool_chafa:
            return self._report_missing_tool("chafa", "previewing images in terminal", con)

        suffix = path.suffix.lower()
        if suffix == ".svg":
            # 1. Try resvg (Yazi's preferred SVG rasterizer)
            tool_resvg = _resolve_tool_executable("resvg")
            if tool_resvg:
                with tempfile.TemporaryDirectory(prefix="kapsel_svg_") as tmp_dir:
                    cache_png = Path(tmp_dir) / "svg_render.png"
                    res = subprocess.run(
                        [tool_resvg, "-w", "800", "-h", "600", "--image-rendering", "optimizeSpeed", str(path), str(cache_png)],
                        capture_output=True,
                    )
                    if res.returncode == 0 and cache_png.exists():
                        return subprocess.run(
                            [tool_chafa, "--format=sixels", "--colors=full", str(cache_png)]
                        ).returncode

            # 2. Try magick for SVG
            tool_magick = _resolve_tool_executable("magick")
            if tool_magick:
                with tempfile.TemporaryDirectory(prefix="kapsel_svg_") as tmp_dir:
                    cache_png = Path(tmp_dir) / "svg_render.png"
                    res = subprocess.run([tool_magick, str(path), str(cache_png)], capture_output=True)
                    if res.returncode == 0 and cache_png.exists():
                        return subprocess.run(
                            [tool_chafa, "--format=sixels", "--colors=full", str(cache_png)]
                        ).returncode

        # Direct native Sixel rendering; Chafa chooses the terminal view size.
        return subprocess.run([tool_chafa, "--format=sixels", "--colors=full", str(path)]).returncode

    def _exec_pdf(self, path: Path, con: Console, page: int = 1) -> int:
        """
        PDF preview via pdftoppm -> page.jpg -> chafa (Yazi's pdf.lua pattern).
        Generates a high-fidelity single JPEG frame of the page and outputs through chafa.
        Fallback: pdftotext or pdf-cli.
        """
        tool_pdftoppm = _resolve_tool_executable("pdftoppm")
        tool_chafa = _resolve_tool_executable("chafa")

        # 1. Primary: Yazi style pdftoppm -> jpeg -> chafa
        if tool_pdftoppm and tool_chafa:
            with tempfile.TemporaryDirectory(prefix="kapsel_pdf_") as tmp_dir:
                out_prefix = Path(tmp_dir) / f"page_{page}"
                conv_res = subprocess.run(
                    [tool_pdftoppm, "-f", str(page), "-l", str(page), "-singlefile", "-jpeg", "-jpegopt", "quality=90", str(path), str(out_prefix)],
                    capture_output=True,
                )
                jpg_file = Path(str(out_prefix) + ".jpg")
                if conv_res.returncode == 0 and jpg_file.exists():
                    con.print(f"[dim italic]📄 {path.name} (Page {page})[/]")
                    return subprocess.run([tool_chafa, str(jpg_file)]).returncode

        # 2. Alternative CLI tools (pdf-cli)
        tool = _resolve_tool_executable("pdf-cli")
        if tool:
            return subprocess.run([tool, str(path)]).returncode

        # 3. Fallback: Text mode via pdftotext
        tool_pdftotext = _resolve_tool_executable("pdftotext")
        if tool_pdftotext:
            con.print(f"[dim italic]📄 {path.name} (Text Mode via pdftotext)[/]")
            return subprocess.run([tool_pdftotext, "-layout", "-f", str(page), "-l", str(page), str(path), "-"]).returncode

        return self._report_missing_tool("pdftoppm (poppler) and chafa", "visually previewing PDF documents in terminal", con)

    def _exec_media(self, path: Path, con: Console) -> int:
        """
        Media Audio/Video preview.
        Yazi pattern:
        1. For video files: Uses ffmpeg to extract a keyframe at offset, rendering an image thumbnail via chafa!
        2. Audio or metadata inspection: displays stream info via mediainfo or ffprobe.
        """
        suffix = path.suffix.lower()
        is_video = suffix in (".mp4", ".mkv", ".avi", ".mov", ".flv", ".wmv", ".webm")

        tool_ffmpeg = _resolve_tool_executable("ffmpeg")
        tool_chafa = _resolve_tool_executable("chafa")

        # Visual thumbnail snapshot for videos (Yazi video.lua approach)
        if is_video and tool_ffmpeg and tool_chafa:
            with tempfile.TemporaryDirectory(prefix="kapsel_video_") as tmp_dir:
                thumb_jpg = Path(tmp_dir) / "thumbnail.jpg"
                cmd = [
                    tool_ffmpeg,
                    "-v", "warning",
                    "-hwaccel", "auto",
                    "-threads", "1",
                    "-an", "-sn", "-dn",
                    "-ss", "00:00:02",
                    "-skip_frame", "nokey",
                    "-i", str(path),
                    "-vframes", "1",
                    "-f", "image2",
                    "-y", str(thumb_jpg),
                ]
                res = subprocess.run(cmd, capture_output=True)
                if res.returncode == 0 and thumb_jpg.exists():
                    con.print(f"[dim italic]🎬 Video Snapshot: {path.name}[/]")
                    subprocess.run([tool_chafa, "--size=80x25", str(thumb_jpg)])

        # Metadata inspection via mediainfo or ffprobe
        tool_media = _resolve_tool_executable("mediainfo")
        if tool_media:
            return subprocess.run([tool_media, str(path)]).returncode

        tool_probe = _resolve_tool_executable("ffprobe")
        if tool_probe:
            return subprocess.run([tool_probe, "-hide_banner", str(path)]).returncode

        return self._report_missing_tool("mediainfo (or ffprobe)", "inspecting media files", con)

    def _exec_binary(self, path: Path, con: Console) -> int:
        """Category 9: Binary inspection via xxd or hexdump."""
        tool_xxd = _resolve_tool_executable("xxd")
        if tool_xxd:
            return subprocess.run([tool_xxd, "-l", "128", str(path)]).returncode

        tool_hex = _resolve_tool_executable("hexdump")
        if tool_hex:
            return subprocess.run([tool_hex, "-C", "-n", "128", str(path)]).returncode

        return self._report_missing_tool("xxd (or hexdump)", "inspecting binary files", con)

    def _exec_code(self, path: Path, con: Console, lines_limit: Optional[int] = None) -> int:
        """Category 10: Code and plaintext preview via bat."""
        tool = _resolve_tool_executable("bat")
        if tool:
            cmd = [tool, "--style=numbers,changes", "--color=always"]
            if lines_limit is not None and lines_limit > 0:
                cmd.extend(["--line-range", f":{lines_limit}"])
            cmd.append(str(path))
            return subprocess.run(cmd).returncode

        return self._report_missing_tool("bat", "previewing code and text files", con)

    def _render_help(self, con: Console) -> None:
        """Renders help information for preview command."""
        con.print("\n[bold #00f0ff]Kapsel Preview (prev) - Universal Smart Terminal Preview Dispatcher[/]")
        con.print("[dim]Maps file categories directly to dedicated CLI tools (inspired by Yazi).[/]\n")
        con.print("[bold white]Usage:[/]")
        con.print("  [#38bdf8]fm[/] [path]               Interactive 3-column Miller Columns file manager")
        con.print("  [#38bdf8]prev[/] <path>             Quick preview (auto-detects tool)")
        con.print("  [#38bdf8]prev[/] -l <n> <path>      Limit preview to first n lines")
        con.print("  [#38bdf8]kps preview fm[/] [path]   Explicit interactive directory manager")
        con.print("  [#38bdf8]kps preview[/] <path>     Explicit preview command\n")
        con.print("[bold white]Supported Categories & Tools (Yazi Toolchain):[/]")
        con.print("  • Code & Text:       [#10b981]bat[/]")
        con.print("  • Markdown:          [#10b981]glow[/]")
        con.print("  • Tabular (CSV/TSV): [#10b981]xsv[/]")
        con.print("  • Structured (JSON): [#10b981]jq[/] (with bat fallback)")
        con.print("  • Directories:       [#10b981]eza[/] / tree")
        con.print("  • Archives:          [#10b981]7zz / 7z[/] / tar (with piped tarball inspection)")
        con.print("  • Fonts (.ttf/.otf): [#10b981]magick + chafa[/] (specimen rendering)")
        con.print("  • Images & SVG:      [#10b981]chafa / resvg / magick[/]")
        con.print("  • PDF Documents:     [#10b981]pdftoppm + chafa[/] / pdf-cli")
        con.print("  • Videos & Audio:    [#10b981]ffmpeg + chafa[/] (keyframe) / mediainfo / ffprobe")
        con.print("  • Binaries:          [#10b981]xxd[/] / hexdump\n")


Plugin = PreviewPlugin
