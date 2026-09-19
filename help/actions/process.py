"""
Process Inspector and Terminator for Help Plugin.
Queries active processes with interactive selection to kill target PIDs.
All comments and docstrings are in English.
"""

import csv
import io
import os
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple

from rich.console import Console
from rich.table import Table

try:
    from ..ui import select_interactive_item
    from .port import terminate_pid
except ImportError:
    from plugins.help.ui import select_interactive_item
    from plugins.help.actions.port import terminate_pid


def get_processes_fallback(filter_term: Optional[str] = None) -> List[Dict[str, Any]]:
    """Fetches process list using system native tools."""
    procs: List[Dict[str, Any]] = []
    is_win = sys.platform == "win32"
    f_lower = filter_term.lower() if filter_term else None

    try:
        if is_win:
            res = subprocess.run(
                ["tasklist", "/fo", "csv", "/nh"],
                capture_output=True,
                text=True,
                errors="replace",
            )
            if res.returncode == 0:
                reader = csv.reader(io.StringIO(res.stdout))
                for row in reader:
                    if len(row) >= 5:
                        name = row[0]
                        pid_str = row[1]
                        mem = row[4]
                        if f_lower and (f_lower not in name.lower() and f_lower != pid_str):
                            continue
                        if pid_str.isdigit():
                            procs.append({
                                "pid": int(pid_str),
                                "name": name,
                                "mem": mem,
                                "cpu": "-",
                            })
        else:
            res = subprocess.run(
                ["ps", "-eo", "pid,%cpu,%mem,comm", "--sort=-%mem"],
                capture_output=True,
                text=True,
                errors="replace",
            )
            if res.returncode == 0:
                lines = res.stdout.strip().splitlines()
                for line in lines[1:]:
                    parts = line.split(maxsplit=3)
                    if len(parts) >= 4:
                        pid_str, cpu, mem, name = parts[0], parts[1], parts[2], parts[3]
                        if f_lower and (f_lower not in name.lower() and f_lower != pid_str):
                            continue
                        if pid_str.isdigit():
                            procs.append({
                                "pid": int(pid_str),
                                "name": name,
                                "mem": f"{mem}%",
                                "cpu": f"{cpu}%",
                            })
    except Exception:
        pass

    return procs


def handle_process(args: List[str], console: Optional[Console] = None) -> int:
    """
    Handles 'kps help ps [filter]'
    """
    con = console or Console(legacy_windows=False)
    filter_arg = args[0] if args else None

    # Check if 'procs' is installed and no interactive selection is demanded
    procs_bin = shutil.which("procs")
    if procs_bin and not sys.stdin.isatty():
        cmd = [procs_bin] + args
        try:
            return subprocess.run(cmd).returncode
        except Exception:
            pass

    con.print(f"[dim]Listing active processes{' matching ' + repr(filter_arg) if filter_arg else ''}...[/]")
    process_list = get_processes_fallback(filter_arg)

    if not process_list:
        con.print("[yellow]No matching processes found.[/yellow]\n")
        return 0

    # Render Table
    table = Table(title="Active Processes", border_style="cyan", header_style="bold #00f0ff")
    table.add_column("PID", style="bold #10b981", justify="right", width=8)
    table.add_column("Process Name", style="bold white")
    table.add_column("Memory", style="#fbbf24", justify="right")
    table.add_column("CPU", style="#38bdf8", justify="right")

    for p in process_list[:30]:
        table.add_row(str(p["pid"]), p["name"], p["mem"], p["cpu"])

    con.print(table)
    if len(process_list) > 30:
        con.print(f"[dim]... and {len(process_list) - 30} more processes.[/dim]")

    # Interactive Kill Menu
    if sys.stdin.isatty():
        menu_items = [
            {
                "label": f"{p['name']} (PID: {p['pid']})",
                "desc": f"Mem: {p['mem']} | CPU: {p['cpu']}",
                "tag": "KILL",
                "pid": p["pid"],
                "name": p["name"],
            }
            for p in process_list[:40]
        ]

        selection = select_interactive_item(
            menu_items,
            title="⚡ Select a Process to Terminate (Kill):",
            key_labels=[("[Enter]", "Kill"), ("[Esc]", "Exit")],
        )

        if selection:
            idx, _ = selection
            chosen = menu_items[idx]
            target_pid = chosen["pid"]
            ok, msg = terminate_pid(target_pid, force=False)
            if ok:
                con.print(f"[bold green]✔ {msg}[/bold green] ({chosen['name']})")
            else:
                con.print(f"[bold red]✖ {msg}[/bold red]")

    return 0


def handle_kill(args: List[str], console: Optional[Console] = None) -> int:
    """Handles explicit 'kps help kill <pid>'"""
    con = console or Console(legacy_windows=False)
    if not args:
        con.print("[yellow]Usage: kps help kill <pid> [--force / -f][/yellow]")
        return 1

    pid_str = args[0]
    if not pid_str.isdigit():
        con.print(f"[bold red]Error: Invalid PID '{pid_str}'. Must be a positive integer.[/bold red]")
        return 1

    force = ("-f" in args) or ("--force" in args)
    pid = int(pid_str)
    ok, msg = terminate_pid(pid, force=force)
    if ok:
        con.print(f"[bold green]✔ {msg}[/bold green]")
        return 0
    else:
        con.print(f"[bold red]✖ {msg}[/bold red]")
        return 1
