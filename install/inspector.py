"""
Post-Install Package Inspector for Kapsel Install Plugin.
Inspects newly installed packages, resolving binary path, version, file size,
and rendering a high-fidelity Rich Panel summary card.

All comments and docstrings are in English.
"""

import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table


def format_size(bytes_size: int) -> str:
    """Formats bytes into human-readable units (KB, MB, GB)."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.1f} PB"


def resolve_binary_location(bin_name: str) -> Optional[Path]:
    """
    Locates the physical binary path across standard PATH and known package manager locations.
    """
    # 1. System PATH
    found = shutil.which(bin_name)
    if found:
        return Path(found)

    is_win = sys.platform == "win32"
    exe_name = f"{bin_name}.exe" if is_win else bin_name

    # 2. Windows specific locations
    if is_win:
        user_home = Path(os.environ.get("USERPROFILE", Path.home()))
        candidates = [
            user_home / "scoop" / "shims" / exe_name,
            user_home / "scoop" / "apps" / bin_name / "current" / exe_name,
            user_home / "AppData" / "Local" / "Microsoft" / "WinGet" / "Links" / exe_name,
            user_home / ".cargo" / "bin" / exe_name,
            user_home / ".kapsel" / "bin" / exe_name,
        ]
        for c in candidates:
            if c.is_file():
                return c
    else:
        # 3. Unix specific locations
        user_home = Path(os.environ.get("HOME", Path.home()))
        candidates = [
            Path("/opt/homebrew/bin") / exe_name,
            Path("/usr/local/bin") / exe_name,
            Path("/usr/bin") / exe_name,
            user_home / ".cargo" / "bin" / exe_name,
            user_home / ".kapsel" / "bin" / exe_name,
        ]
        for c in candidates:
            if c.is_file():
                return c

    return None


def probe_binary_version(bin_path: Path) -> Optional[str]:
    """Probes the binary version by calling --version or -V."""
    for flag in ["--version", "-V", "-v", "version"]:
        try:
            res = subprocess.run(
                [str(bin_path), flag],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=2,
            )
            out = res.stdout.strip() or res.stderr.strip()
            if out:
                # Extract first line
                first_line = out.splitlines()[0].strip()
                if len(first_line) < 80:
                    return first_line
        except Exception:
            continue
    return None


def inspect_installed_package(
    package_id: str,
    manager: str,
    bin_name: Optional[str] = None,
    version: Optional[str] = None,
    console: Optional[Console] = None,
) -> None:
    """
    Inspects and displays a Rich Panel card for a newly installed package.
    """
    con = console or Console(legacy_windows=False)
    target_bin = bin_name or package_id

    # Resolve binary
    bin_path = resolve_binary_location(target_bin)
    resolved_version = version

    file_size_str = "Unknown"
    if bin_path and bin_path.exists():
        try:
            sz = bin_path.stat().st_size
            file_size_str = format_size(sz)
        except Exception:
            pass

        if not resolved_version:
            probed = probe_binary_version(bin_path)
            if probed:
                resolved_version = probed

    # Construct Inspector Table
    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="dim bold white", justify="right", width=14)
    grid.add_column(style="cyan")

    grid.add_row("Package:", f"[bold white]{package_id}[/]")
    grid.add_row("Manager:", f"[bold #38bdf8]{manager}[/]")
    if resolved_version:
        grid.add_row("Version:", f"[bold green]{resolved_version}[/]")
    if bin_path:
        grid.add_row("Binary Path:", f"[bold #f59e0b]{bin_path}[/]")
        grid.add_row("Binary Size:", f"[dim]{file_size_str}[/]")
    else:
        grid.add_row("Status:", "[yellow]Binary not yet in current shell PATH (refresh shell to update)[/]")

    grid.add_row("Quickstart:", f"[dim]Run '[bold #00f0ff]{target_bin} --help[/]' to inspect command options.[/]")

    panel = Panel(
        grid,
        title=f"[bold #10b981]✔ Package Successfully Installed: {package_id}[/]",
        title_align="left",
        border_style="#10b981",
        padding=(1, 2),
    )

    con.print("")
    con.print(panel)
    con.print("")
