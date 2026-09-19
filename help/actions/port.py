"""
Port Occupancy Inspector and Process Terminator for Help Plugin.
Inspects which process is listening on or occupying a specific TCP/UDP port,
with one-key interactive process termination.
All comments and docstrings are in English.
"""

import os
import re
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

try:
    from ..ui import select_interactive_item
except ImportError:
    from plugins.help.ui import select_interactive_item


def get_process_name_by_pid(pid: int) -> str:
    """Resolves process name from PID."""
    if pid <= 0:
        return "System"
    try:
        if sys.platform == "win32":
            res = subprocess.run(
                ["tasklist", "/fi", f"PID eq {pid}", "/fo", "csv", "/nh"],
                capture_output=True,
                text=True,
                errors="replace",
            )
            if res.returncode == 0 and res.stdout.strip():
                line = res.stdout.strip().splitlines()[0]
                parts = [p.strip(' "') for p in line.split('","')]
                if parts and parts[0]:
                    return parts[0]
        else:
            res = subprocess.run(
                ["ps", "-p", str(pid), "-o", "comm="],
                capture_output=True,
                text=True,
                errors="replace",
            )
            if res.returncode == 0 and res.stdout.strip():
                return res.stdout.strip()
    except Exception:
        pass
    return "Unknown"


def query_port(port: int) -> List[Dict[str, Any]]:
    """
    Queries port listeners across operating systems.
    Returns list of dicts: proto, local, foreign, state, pid, name.
    """
    results: List[Dict[str, Any]] = []
    is_win = sys.platform == "win32"

    try:
        if is_win:
            res = subprocess.run(
                ["netstat", "-ano"],
                capture_output=True,
                text=True,
                errors="replace",
            )
            if res.returncode == 0:
                target_token = f":{port}"
                for line in res.stdout.splitlines():
                    tokens = line.strip().split()
                    if len(tokens) >= 4 and target_token in tokens[1]:
                        proto = tokens[0]
                        local = tokens[1]
                        foreign = tokens[2]
                        state = tokens[3] if len(tokens) == 5 else "LISTENING"
                        pid_str = tokens[-1]
                        if pid_str.isdigit():
                            pid = int(pid_str)
                            results.append({
                                "proto": proto,
                                "local": local,
                                "foreign": foreign,
                                "state": state,
                                "pid": pid,
                                "name": get_process_name_by_pid(pid),
                            })
        else:
            # Unix ss / lsof
            if shutil.which("ss"):
                res = subprocess.run(
                    ["ss", "-tlnp", f"sport = :{port}"],
                    capture_output=True,
                    text=True,
                    errors="replace",
                )
                if res.returncode == 0:
                    for line in res.stdout.splitlines()[1:]:
                        tokens = line.split()
                        if len(tokens) >= 4:
                            # Extract pid if available: users:(("name",pid=123,fd=4))
                            pid = 0
                            p_name = "Unknown"
                            match = re.search(r'users:\(\("([^"]+)",pid=(\d+)', line)
                            if match:
                                p_name = match.group(1)
                                pid = int(match.group(2))
                            results.append({
                                "proto": tokens[0],
                                "local": tokens[3],
                                "foreign": tokens[4] if len(tokens) > 4 else "*:*",
                                "state": tokens[1],
                                "pid": pid,
                                "name": p_name,
                            })
            elif shutil.which("lsof"):
                res = subprocess.run(
                    ["lsof", "-i", f":{port}", "-P", "-n"],
                    capture_output=True,
                    text=True,
                    errors="replace",
                )
                if res.returncode == 0:
                    for line in res.stdout.splitlines()[1:]:
                        tokens = line.split()
                        if len(tokens) >= 9:
                            p_name = tokens[0]
                            pid = int(tokens[1]) if tokens[1].isdigit() else 0
                            proto = tokens[4]
                            local = tokens[8]
                            state = tokens[9] if len(tokens) > 9 else "LISTEN"
                            results.append({
                                "proto": proto,
                                "local": local,
                                "foreign": "*:*",
                                "state": state,
                                "pid": pid,
                                "name": p_name,
                            })
    except Exception:
        pass

    # Deduplicate results by (proto, local, pid)
    unique: List[Dict[str, Any]] = []
    seen = set()
    for r in results:
        key = (r["proto"], r["local"], r["pid"])
        if key not in seen:
            seen.add(key)
            unique.append(r)

    return unique


def terminate_pid(pid: int, force: bool = False) -> Tuple[bool, str]:
    """Terminates process by PID."""
    if pid <= 0:
        return False, "Invalid PID"
    try:
        if sys.platform == "win32":
            args = ["taskkill", "/pid", str(pid)]
            if force:
                args.append("/f")
            res = subprocess.run(args, capture_output=True, text=True, errors="replace")
            if res.returncode == 0:
                return True, f"Successfully terminated PID {pid}"
            return False, res.stderr.strip() or res.stdout.strip()
        else:
            import signal
            sig = signal.SIGKILL if force else signal.SIGTERM
            os.kill(pid, sig)
            return True, f"Successfully sent signal {sig} to PID {pid}"
    except Exception as e:
        return False, str(e)


def handle_port(args: List[str], console: Optional[Console] = None) -> int:
    """
    Handles 'kps help port <n>' or 'kps help <n>'
    """
    con = console or Console(legacy_windows=False)
    if not args:
        con.print("[yellow]Usage: kps help port <number> [--kill][/yellow]")
        return 1

    port_arg = args[0].lstrip(":")
    if not port_arg.isdigit():
        con.print(f"[bold red]Error: Invalid port number '{args[0]}'. Must be an integer 1-65535.[/bold red]")
        return 1

    port = int(port_arg)
    if not (1 <= port <= 65535):
        con.print(f"[bold red]Error: Port out of range ({port}). Must be 1-65535.[/bold red]")
        return 1

    direct_kill = ("--kill" in args) or ("-k" in args)
    force_kill = ("-f" in args) or ("--force" in args)

    con.print(f"[dim]Inspecting network port [/][bold cyan]:{port}[/][dim]...[/]")
    records = query_port(port)

    if not records:
        con.print(f"[bold green]✔ Port {port} is completely FREE.[/bold green] (No active listeners found)\n")
        return 0

    table = Table(title=f"Port {port} Listeners", border_style="cyan", header_style="bold #00f0ff")
    table.add_column("Proto", style="bold #38bdf8", width=8)
    table.add_column("Local Address", style="#ffffff")
    table.add_column("State", style="#fbbf24")
    table.add_column("PID", style="bold #10b981", justify="right")
    table.add_column("Process Name", style="bold white")

    for r in records:
        table.add_row(r["proto"], r["local"], r["state"], str(r["pid"]), r["name"])

    con.print(table)

    # If direct kill was requested via flag
    if direct_kill:
        for r in records:
            pid = r["pid"]
            if pid > 0:
                ok, msg = terminate_pid(pid, force=force_kill)
                if ok:
                    con.print(f"[bold green]✔ {msg}[/bold green] ({r['name']})")
                else:
                    con.print(f"[bold red]✖ {msg}[/bold red]")
        return 0

    # Interactive Action Flow: Prompt to kill
    if sys.stdin.isatty():
        killable = [r for r in records if r["pid"] > 0]
        if killable:
            menu_items = [
                {
                    "label": f"Kill {r['name']} (PID: {r['pid']})",
                    "desc": f"Terminate {r['proto']} listener on {r['local']}",
                    "tag": "KILL",
                    "pid": r["pid"],
                }
                for r in killable
            ]
            menu_items.append({
                "label": "Exit without action",
                "desc": "Keep port listeners running",
                "tag": "EXIT",
                "pid": 0,
            })

            selection = select_interactive_item(
                menu_items,
                title=f"⚡ Action for Port {port}:",
                key_labels=[("[Enter]", "Kill Process"), ("[Esc]", "Cancel")],
            )
            if selection:
                idx, _ = selection
                chosen = menu_items[idx]
                target_pid = chosen.get("pid", 0)
                if target_pid > 0:
                    ok, msg = terminate_pid(target_pid, force=False)
                    if ok:
                        con.print(f"[bold green]✔ {msg}[/bold green]")
                    else:
                        con.print(f"[bold red]✖ {msg}[/bold red]")

    return 0
