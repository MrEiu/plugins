"""
Core Engine & Business Logic for Kapsel Plugin Template.
Provides canonical patterns for external tool resolution, subprocess execution,
and Rich terminal UI card rendering.
All comments and docstrings are in English.
"""

from pathlib import Path
import os
import shutil
import subprocess
import sys
from typing import Dict, List, Optional, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from kapsel.storage.config import get_kapsel_dir


def resolve_tool_executable(name: str) -> Optional[str]:
    """
    Standard executable resolution pattern across platforms.
    Searches:
    1. System PATH
    2. Local Kapsel bin directory (~/.kapsel/bin)
    3. Windows Scoop, WinGet, and Cargo shims
    4. macOS / Linux Homebrew, usr/bin, and ~/.local/bin
    """
    # 1. Standard system PATH
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

    # 3. Windows-specific user install paths
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


def run_command_safely(
    args: List[str],
    timeout_sec: int = 10,
) -> Tuple[int, str, str]:
    """
    Standard subprocess runner with timeout and utf-8 fallback handling.
    Returns (exit_code, stdout_str, stderr_str).
    """
    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_sec,
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except subprocess.TimeoutExpired:
        return 124, "", "Command execution timed out."
    except Exception as e:
        return 1, "", f"Failed to execute command: {str(e)}"


def render_info_card(
    title: str,
    data: Dict[str, str],
    console: Console,
    status_success: bool = True,
) -> None:
    """
    Renders an informative Rich panel table matching Kapsel styling standards.
    """
    border_color = "#00f0ff" if status_success else "#f43f5e"
    status_icon = "✔" if status_success else "✖"

    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold #38bdf8", justify="right")
    table.add_column(style="white")

    for key, val in data.items():
        table.add_row(f"{key}:", val)

    panel = Panel(
        table,
        title=f"[bold white]{title}[/]",
        subtitle=f"[dim]Kapsel Plugin Template · {status_icon}[/]",
        border_style=border_color,
        padding=(1, 2),
    )
    console.print()
    console.print(panel)
    console.print()
