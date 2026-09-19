"""
Command Locator (which / where / find) for Help Plugin.
Discovers full absolute paths of executables across system PATH, shims, and package managers,
with one-key path copying and direct execution.
All comments and docstrings are in English.
"""

import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.table import Table

try:
    from ..ui import copy_to_clipboard, open_in_file_manager, select_interactive_item
except ImportError:
    from plugins.help.ui import copy_to_clipboard, open_in_file_manager, select_interactive_item


def find_all_binary_paths(name: str) -> List[str]:
    """Finds all occurrences of an executable in system PATH."""
    paths: List[str] = []
    seen = set()

    is_win = sys.platform == "win32"
    tool = "where" if is_win else "which"

    try:
        args = ["where", name] if is_win else ["which", "-a", name]
        res = subprocess.run(args, capture_output=True, text=True, errors="replace")
        if res.returncode == 0:
            for line in res.stdout.splitlines():
                clean = line.strip()
                if clean and clean not in seen and Path(clean).is_file():
                    seen.add(clean)
                    paths.append(clean)
    except Exception:
        pass

    # Fallback to shutil.which if tool didn't find anything
    if not paths:
        w = shutil.which(name)
        if w and w not in seen:
            paths.append(w)

    return paths


def get_binary_version_snippet(path_str: str) -> str:
    """Attempts to get a quick version string from the binary."""
    try:
        for flag in ["--version", "-v", "-V"]:
            res = subprocess.run(
                [path_str, flag],
                capture_output=True,
                text=True,
                errors="replace",
                timeout=1.0,
            )
            if res.returncode == 0 and res.stdout.strip():
                first_line = res.stdout.strip().splitlines()[0]
                if len(first_line) <= 60:
                    return first_line
    except Exception:
        pass
    return ""


def handle_locate(args: List[str], console: Optional[Console] = None) -> int:
    """
    Handles 'kps help which <cmd>' / 'kps help where <cmd>'
    """
    con = console or Console(legacy_windows=False)
    if not args:
        con.print("[yellow]Usage: kps help which <command>[/yellow]")
        return 1

    target = args[0]
    con.print(f"[dim]Locating executable for [/][bold cyan]{target}[/][dim]...[/]")
    matches = find_all_binary_paths(target)

    if not matches:
        con.print(f"[bold red]✖ Command '{target}' not found in PATH.[/bold red]")
        return 1

    # Print results
    table = Table(title=f"Locations for '{target}'", border_style="cyan", header_style="bold #00f0ff")
    table.add_column("Order", style="bold #10b981", width=6)
    table.add_column("Full Binary Path", style="bold white")
    table.add_column("Size", style="#fbbf24", justify="right")
    table.add_column("Version", style="#38bdf8")

    items_for_menu = []
    for idx, p_str in enumerate(matches, start=1):
        p = Path(p_str)
        size_str = f"{p.stat().st_size / (1024 * 1024):.2f} MB" if p.exists() else "Unknown"
        ver_str = get_binary_version_snippet(p_str)
        table.add_row(str(idx), p_str, size_str, ver_str)

        items_for_menu.append({
            "label": p_str,
            "desc": f"{size_str} {ver_str}".strip(),
            "tag": f"#{idx}",
            "path": p_str,
        })

    con.print(table)

    # Interactive Action Flow
    if sys.stdin.isatty():
        selection = select_interactive_item(
            items_for_menu,
            title=f"⚡ Action for '{target}':",
            key_labels=[
                ("[Enter]", "Copy Path"),
                ("[x]", "Run Command"),
                ("[o]", "Open Folder"),
                ("[Esc]", "Exit"),
            ],
            extra_bindings={"x": lambda *_: None, "o": lambda *_: None},
        )

        if selection:
            idx, act_key = selection
            chosen_path = items_for_menu[idx]["path"]

            if act_key in ("enter", "c"):
                if copy_to_clipboard(chosen_path):
                    con.print(f"[bold green]✔ Copied path to clipboard:[/bold green] [cyan]{chosen_path}[/cyan]")
                else:
                    con.print(f"[yellow]Path: {chosen_path}[/yellow]")
            elif act_key == "o":
                if open_in_file_manager(chosen_path):
                    con.print(f"[bold green]✔ Opened containing folder:[/bold green] [dim]{chosen_path}[/dim]")
            elif act_key == "x":
                con.print(f"[bold cyan]Running {chosen_path}...[/bold cyan]\n")
                subprocess.run([chosen_path])

    return 0
