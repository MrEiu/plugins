"""
Command Usage, Cheat Sheets, and Integrated Location Action for Help Plugin.
Bridges tealdeer (tldr) and cheat.sh, automatically locates local binary executables,
extracts practical examples, and allows one-key copying or executing.
All comments and docstrings are in English.
"""

import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from kapsel.storage.config import get_kapsel_dir

try:
    from ..ui import copy_to_clipboard, open_in_file_manager, select_interactive_item
    from .locate import find_all_binary_paths
    from .process import get_processes_fallback
except ImportError:
    from plugins.help.ui import copy_to_clipboard, open_in_file_manager, select_interactive_item
    from plugins.help.actions.locate import find_all_binary_paths
    from plugins.help.actions.process import get_processes_fallback


def resolve_tldr_executable() -> Optional[str]:
    """Locates tealdeer / tldr executable."""
    for name in ("tldr", "tealdeer"):
        p = shutil.which(name)
        if p:
            return p

    bin_dir = get_kapsel_dir() / "bin"
    is_win = sys.platform == "win32"
    for name in ("tldr.exe" if is_win else "tldr", "tealdeer.exe" if is_win else "tealdeer"):
        local_bin = bin_dir / name
        if local_bin.exists():
            return str(local_bin)

    return None


def fetch_cheat_sh(command: str, timeout: float = 4.0) -> Optional[str]:
    """Fetches command cheat sheet from cheat.sh service."""
    url = f"https://cheat.sh/{command}?T"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "curl/7.68.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content = resp.read().decode("utf-8", errors="replace")
            # If cheat.sh returns 404 text or unknown page
            if "Unknown topic" in content or "404 NOT FOUND" in content:
                return None
            return content
    except Exception:
        return None


def extract_examples(text: str) -> List[Dict[str, str]]:
    """
    Extracts example code blocks and descriptions from tldr or cheat.sh output.
    Returns list of dicts: {"desc": ..., "command": ...}
    """
    examples: List[Dict[str, str]] = []
    lines = text.splitlines()

    current_desc = ""
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Pattern 1: tldr description e.g. "- Description text:" or "> Description text"
        if stripped.startswith("- ") or stripped.startswith("> "):
            current_desc = stripped.lstrip("-> :").strip()
            continue

        # Pattern 2: tldr command line e.g. "`cmd --flag`" or indented "cmd --flag"
        if stripped.startswith("`") and stripped.endswith("`"):
            cmd_text = stripped.strip("`").strip()
            examples.append({"desc": current_desc or "Example usage", "command": cmd_text})
            current_desc = ""
            continue

        if line.startswith("  ") and not stripped.startswith("#") and not stripped.startswith("-"):
            # Indented code line
            examples.append({"desc": current_desc or "Example usage", "command": stripped})
            current_desc = ""
            continue

        # Pattern 3: cheat.sh comment e.g. "# To do something:"
        if stripped.startswith("# "):
            current_desc = stripped.lstrip("# :").strip()

    return examples


def handle_cheat(args: List[str], console: Optional[Console] = None) -> int:
    """
    Handles 'kps help <cmd>' or 'kps help cheat <cmd>'
    """
    con = console or Console(legacy_windows=False)
    if not args:
        con.print("[yellow]Usage: kps help <command>[/yellow]")
        return 1

    cmd_name = args[0]
    sub_args = args[1:]

    # 1. Inspect local binary location and active running processes
    bin_paths = find_all_binary_paths(cmd_name)
    running_procs = get_processes_fallback(cmd_name)

    # 2. Render Context Banner
    header_parts = []
    if bin_paths:
        header_parts.append(f"📍 [bold #38bdf8]Location:[/] [dim]{bin_paths[0]}[/dim]")
    if running_procs:
        pids_str = ", ".join(str(p["pid"]) for p in running_procs[:3])
        if len(running_procs) > 3:
            pids_str += f" (+{len(running_procs) - 3})"
        header_parts.append(f"💡 [bold #10b981]Active:[/] [yellow]{len(running_procs)} process(es) running[/yellow] (PID: {pids_str})")

    if header_parts:
        banner_content = "  •  ".join(header_parts)
        con.print(Panel(banner_content, border_style="cyan", padding=(0, 1)))

    # 3. Query tldr / cheat.sh
    output_text = ""
    tldr_bin = resolve_tldr_executable()
    used_engine = "tealdeer"

    if tldr_bin:
        try:
            res = subprocess.run([tldr_bin, cmd_name] + sub_args, capture_output=True, text=True, errors="replace")
            if res.returncode == 0 and res.stdout.strip():
                output_text = res.stdout
        except Exception:
            pass

    if not output_text:
        # Fallback to cheat.sh HTTP API
        cheat_res = fetch_cheat_sh(cmd_name)
        if cheat_res:
            output_text = cheat_res
            used_engine = "cheat.sh"

    if not output_text:
        if bin_paths:
            con.print(f"[yellow]No cheat sheet found for '{cmd_name}', but executable exists locally at:[/yellow]")
            for p in bin_paths:
                con.print(f"  • [cyan]{p}[/cyan]")
            return 0
        con.print(f"[bold red]✖ No cheat sheet or command found for '{cmd_name}'.[/bold red]")
        con.print("[dim]Try running:[/] [bold cyan]kapsel add help[/bold cyan] [dim]to update local cache.[/dim]")
        return 1

    # Print raw page content
    con.print(output_text.rstrip())

    # 4. Interactive Action Flow: Extract examples
    examples = extract_examples(output_text)

    if sys.stdin.isatty() and (examples or bin_paths or running_procs):
        menu_items: List[Dict[str, Any]] = []

        for ex in examples[:12]:
            menu_items.append({
                "label": ex["command"],
                "desc": ex["desc"],
                "tag": "RUN/COPY",
                "action": "example",
                "cmd": ex["command"],
            })

        if bin_paths:
            menu_items.append({
                "label": f"Copy Binary Path ({bin_paths[0]})",
                "desc": "Copy executable absolute path to clipboard",
                "tag": "PATH",
                "action": "copy_path",
                "path": bin_paths[0],
            })
            menu_items.append({
                "label": "Open Containing Directory",
                "desc": f"Reveal {bin_paths[0]} in file manager",
                "tag": "EXPLORER",
                "action": "open_folder",
                "path": bin_paths[0],
            })

        if running_procs:
            menu_items.append({
                "label": f"Inspect / Terminate Active Processes ({len(running_procs)} running)",
                "desc": f"Kill {cmd_name} processes",
                "tag": "KILL",
                "action": "jump_ps",
            })

        key_labels = [
            ("[Enter]", "Copy"),
            ("[x]", "Execute"),
            ("[Esc]", "Exit"),
        ]

        selection = select_interactive_item(
            menu_items,
            title=f"⚡ Interactive Actions for '{cmd_name}':",
            key_labels=key_labels,
            extra_bindings={"x": lambda *_: None},
        )

        if selection:
            idx, act_key = selection
            chosen = menu_items[idx]
            act = chosen.get("action")

            if act == "example":
                cmd_text = chosen["cmd"]
                if act_key == "x":
                    con.print(f"\n[bold cyan]Executing:[/] [bold white]{cmd_text}[/]\n")
                    subprocess.run(cmd_text, shell=True)
                else:
                    if copy_to_clipboard(cmd_text):
                        con.print(f"\n[bold green]✔ Copied example to clipboard:[/] [cyan]{cmd_text}[/cyan]")
                    else:
                        con.print(f"\n[dim]Command:[/] {cmd_text}")
            elif act == "copy_path":
                p_str = chosen["path"]
                if copy_to_clipboard(p_str):
                    con.print(f"\n[bold green]✔ Copied path to clipboard:[/] [cyan]{p_str}[/cyan]")
            elif act == "open_folder":
                open_in_file_manager(chosen["path"])
                con.print(f"\n[bold green]✔ Opened containing folder.[/bold green]")
            elif act == "jump_ps":
                from .process import handle_process
                con.print("\n")
                return handle_process([cmd_name], console=con)

    return 0
