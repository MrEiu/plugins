"""
Translate Engine for Kapsel Translate Plugin.
Supports multi-backend translation:
1. Windows: Native 'fanyi' CLI (powered by iciba, youdao, and LLM).
2. Linux / macOS: 'translate-shell' (trans) or 'fanyi'.
All comments and docstrings are in English.
"""

from pathlib import Path
import os
import re
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from kapsel.storage.config import get_kapsel_dir


def resolve_fanyi_executable() -> Optional[str]:
    """
    Locates the 'fanyi' executable across system PATH, npm global paths,
    Python nodejs_wheel directory, and ~/.kapsel/bin.
    """
    is_win = sys.platform == "win32"
    names = ["fanyi.cmd", "fanyi", "fy.cmd", "fy"] if is_win else ["fanyi", "fy"]

    # 1. System PATH
    for name in names:
        p = shutil.which(name)
        if p:
            return p

    user_home = Path(os.environ.get("USERPROFILE" if is_win else "HOME", Path.home()))

    # 2. Local Kapsel bin directory (~/.kapsel/bin)
    for name in names:
        local_bin = get_kapsel_dir() / "bin" / name
        if local_bin.exists():
            return str(local_bin)

    # 3. Windows-specific user paths (nodejs_wheel, npm, AppData)
    if is_win:
        candidates = [
            Path("C:/Users/meru6/AppData/Local/Programs/Python/Python313/Lib/site-packages/nodejs_wheel/fanyi.cmd"),
            user_home / "AppData" / "Roaming" / "npm" / "fanyi.cmd",
            user_home / "AppData" / "Local" / "Yarn" / "bin" / "fanyi.cmd",
            user_home / "AppData" / "Local" / "pnpm" / "fanyi.cmd",
            user_home / "scoop" / "shims" / "fanyi.cmd",
        ]
        # Also check python site-packages for nodejs_wheel dynamically
        try:
            for sys_p in sys.path:
                cand = Path(sys_p) / "nodejs_wheel" / "fanyi.cmd"
                if cand.exists():
                    candidates.insert(0, cand)
        except Exception:
            pass

        for cand in candidates:
            if cand.exists():
                return str(cand)
    else:
        # 4. Unix npm / yarn / pnpm paths
        unix_candidates = [
            Path("/usr/local/bin/fanyi"),
            Path("/usr/bin/fanyi"),
            user_home / ".npm-global" / "bin" / "fanyi",
            user_home / ".local" / "bin" / "fanyi",
        ]
        for cand in unix_candidates:
            if cand.exists():
                return str(cand)

    return None


def resolve_trans_executable() -> Optional[str]:
    """
    Locates the 'trans' executable across system PATH, ~/.kapsel/bin,
    Scoop, WinGet, Cargo, and Unix paths.
    """
    p = shutil.which("trans")
    if p:
        return p

    is_win = sys.platform == "win32"
    exe_name = "trans.exe" if is_win else "trans"

    local_bin = get_kapsel_dir() / "bin" / exe_name
    if local_bin.exists():
        return str(local_bin)

    user_home = Path(os.environ.get("USERPROFILE" if is_win else "HOME", Path.home()))

    if is_win:
        candidates = [
            user_home / "scoop" / "shims" / exe_name,
            user_home / "scoop" / "apps" / "translate-shell" / "current" / exe_name,
            user_home / "AppData" / "Local" / "Microsoft" / "WinGet" / "Links" / exe_name,
            Path("C:/Program Files/Git/usr/bin") / exe_name,
            Path("C:/Git/usr/bin") / exe_name,
        ]
        for candidate in candidates:
            if candidate.exists():
                return str(candidate)
    else:
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


def resolve_translator_executable() -> Tuple[str, Optional[str]]:
    """
    Determines the best translation engine for the current platform:
    - On Windows: prefers 'fanyi' (native, robust, zero WSL required), then 'trans'.
    - On Unix/macOS: prefers 'trans', then 'fanyi'.
    Returns (engine_type, path).
    """
    is_win = sys.platform == "win32"
    if is_win:
        fanyi = resolve_fanyi_executable()
        if fanyi:
            return "fanyi", fanyi
        trans = resolve_trans_executable()
        if trans:
            return "trans", trans
        return "none", None
    else:
        trans = resolve_trans_executable()
        if trans:
            return "trans", trans
        fanyi = resolve_fanyi_executable()
        if fanyi:
            return "fanyi", fanyi
        return "none", None


def contains_cjk(text: str) -> bool:
    """Returns True if the text contains Chinese/Japanese/Korean characters."""
    return bool(re.search(r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]", text))


def detect_target_language(text: str, explicit_target: Optional[str] = None) -> str:
    """
    Returns explicit target if specified, otherwise auto-selects:
    - If text contains CJK -> translate to English ('en')
    - Otherwise -> translate to Simplified Chinese ('zh-CN')
    """
    if explicit_target:
        return explicit_target
    return "en" if contains_cjk(text) else "zh-CN"


def clean_fanyi_output(raw_output: str) -> str:
    """
    Cleans up noisy intermediate lines from fanyi CLI (e.g. search spinners and headers),
    retaining the clean translation and dictionary definitions.
    """
    lines = [line.strip() for line in raw_output.splitlines()]
    clean_lines = []
    for line in lines:
        if not line:
            if clean_lines and clean_lines[-1] != "":
                clean_lines.append("")
            continue
        # Skip search progress indicators and missed dictionary notices
        if (
            line.startswith("- 正在请教")
            or "未找到" in line
            or line.startswith("npm warn")
            or line.startswith("node:")
        ):
            continue
        clean_lines.append(line)

    result = "\n".join(clean_lines).strip()
    return result if result else raw_output.strip()


def execute_fanyi(
    tool_path: str,
    text: str,
    timeout_sec: int = 15,
) -> Tuple[int, str]:
    """Executes 'fanyi' CLI and returns cleaned translation."""
    try:
        proc = subprocess.run(
            [tool_path, text],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_sec,
        )
        if proc.returncode == 0:
            cleaned = clean_fanyi_output(proc.stdout)
            return 0, cleaned
        err = proc.stderr.strip() or proc.stdout.strip()
        return proc.returncode, clean_fanyi_output(err)
    except subprocess.TimeoutExpired:
        return 124, "Translation timed out (network connection issue)."
    except Exception as e:
        return 1, f"Execution failed: {str(e)}"


def execute_trans(
    text: str,
    target_lang: Optional[str] = None,
    source_lang: Optional[str] = None,
    brief: bool = True,
    timeout_sec: int = 15,
) -> Tuple[int, str]:
    """
    Universal translation entry point.
    Dispatches to 'fanyi' on Windows or 'trans' on Linux/macOS.
    """
    engine, tool = resolve_translator_executable()
    if not tool:
        return 127, "Error: No translation engine found (fanyi or translate-shell)."

    if engine == "fanyi":
        return execute_fanyi(tool, text, timeout_sec=timeout_sec)

    # POSIX translate-shell execution
    resolved_target = detect_target_language(text, target_lang)
    lang_spec = f"{source_lang or ''}:{resolved_target}"

    cmd = [tool, "-no-ansi"]
    if brief:
        cmd.append("-b")
    cmd.extend([lang_spec, text])

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_sec,
        )
        if proc.returncode == 0:
            return 0, proc.stdout.strip()
        err_msg = proc.stderr.strip() or proc.stdout.strip()
        return proc.returncode, err_msg
    except subprocess.TimeoutExpired:
        return 124, "Translation timed out (network connection issue)."
    except Exception as e:
        return 1, f"Execution failed: {str(e)}"


def get_last_command_block() -> Optional[Any]:
    """
    Retrieves the most recent command block that wasn't a 'tr' or 'trans' invocation.
    """
    try:
        from kapsel.core.block.registry import get_block_registry
        reg = get_block_registry()
        blocks = reg.get_blocks()
        if not blocks:
            return None

        for block in reversed(blocks):
            cmd = block.command.strip()
            if not cmd.startswith("tr ") and cmd != "tr" and not cmd.startswith("kps tr") and not cmd.startswith("kps trans"):
                return block
        return None
    except Exception:
        return None


def extract_key_output_for_translation(block: Any, max_lines: int = 25) -> Tuple[str, bool]:
    """
    Smartly extracts the most relevant snippet of output for translation.
    If the block failed, prioritizes error lines and stack traces.
    Returns (extracted_text, is_error_prioritized).
    """
    lines = list(getattr(block, "_output_lines", []))
    if not lines and hasattr(block, "output_text") and block.output_text:
        lines = block.output_text.splitlines()

    if not lines:
        return "", False

    is_failed = getattr(block, "exit_code", 0) != 0

    if is_failed:
        error_keywords = ("error", "failed", "fatal", "exception", "traceback", "cannot", "denied", "undefined", "syntaxerror", "refused")
        matching_indices = [
            i for i, line in enumerate(lines)
            if any(k in line.lower() for k in error_keywords)
        ]
        if matching_indices:
            start_idx = max(0, matching_indices[0] - 2)
            end_idx = min(len(lines), matching_indices[-1] + 5)
            snippet_lines = lines[start_idx:end_idx]
            if len(snippet_lines) > max_lines:
                snippet_lines = snippet_lines[-max_lines:]
            return "\n".join(snippet_lines), True

    tail = lines[-max_lines:] if len(lines) > max_lines else lines
    return "\n".join(tail), False


def render_translation_card(
    command: str,
    exit_code: int,
    original: str,
    translated: str,
    console: Console,
    target_lang: str = "zh-CN",
) -> None:
    """Renders a modern Rich bilingual translation card for command outputs."""
    status_icon = "✔" if exit_code == 0 else "✖"
    status_color = "#10b981" if exit_code == 0 else "#f43f5e"

    title = f"[bold white]🌐 Command Output Translation[/] [dim]({target_lang})[/]"
    subtitle = f"[{status_color}]{status_icon} exit {exit_code}[/] [dim]·[/] [bold #38bdf8]{command}[/]"

    table = Table.grid(padding=(0, 1))
    table.add_column(style="bold #94a3b8", justify="right", width=6)
    table.add_column(style="white")

    orig_clean = original.strip()
    if len(orig_clean) > 800:
        orig_clean = orig_clean[:800] + "\n[dim]...(truncated)...[/]"

    table.add_row("[#64748b]原文[/]", f"[dim]{orig_clean}[/]")
    table.add_row("", "")
    table.add_row("[#38bdf8]译文[/]", f"[bold #f1f5f9]{translated.strip()}[/]")

    panel = Panel(
        table,
        title=title,
        subtitle=subtitle,
        border_style="#0284c7",
        padding=(1, 2),
    )
    console.print()
    console.print(panel)
    console.print()


def render_text_translation(
    source_text: str,
    translated_text: str,
    target_lang: str,
    console: Console,
) -> None:
    """Renders inline translation for direct text queries."""
    console.print(f"\n[dim]# {source_text}[/]")
    console.print(f"[bold #00f0ff]❯[/] [bold white]{translated_text}[/] [dim]({target_lang})[/]\n")
