"""
Autopilot (Background Task Queue & Autonomous Execution) Plugin for Kapsel.
Bridges Pueue (daemon and CLI) to provide zero-friction background task execution,
queue orchestration, live logging, and process lifecycle management.
Exposes functional commands under the 'kps auto' namespace.
All comments and descriptions are in English.
"""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from kapsel.core.plugin.base import KapselPlugin, PluginManifest
from kapsel.core.plugin.context import PluginContext
from kapsel.core.plugin.hooks import HookType
from kapsel.storage.config import get_kapsel_dir
from kapsel.ui.banner import ensure_utf8_io

ensure_utf8_io()


def _resolve_pueue_executables() -> Tuple[Optional[str], Optional[str]]:
    """
    Locates 'pueue' (CLI client) and 'pueued' (daemon) executables:
    1. Scoop direct app path
    2. Scoop shims / System PATH
    3. Local Kapsel bin directory (~/.kapsel/bin)
    """
    is_win = sys.platform == "win32"
    ext = ".exe" if is_win else ""

    pueue_bin: Optional[str] = None
    pueued_bin: Optional[str] = None

    # 1. Direct Scoop app path
    user_home = Path.home()
    scoop_current = user_home / "scoop" / "apps" / "pueue" / "current"
    if (scoop_current / f"pueue{ext}").exists():
        pueue_bin = str(scoop_current / f"pueue{ext}")
    if (scoop_current / f"pueued{ext}").exists():
        pueued_bin = str(scoop_current / f"pueued{ext}")

    # 2. System PATH & Scoop shims
    if not pueue_bin:
        pueue_bin = shutil.which("pueue")
    if not pueued_bin:
        pueued_bin = shutil.which("pueued")

    # 3. Local Kapsel bin directory
    kapsel_bin = get_kapsel_dir() / "bin"
    if not pueue_bin and (kapsel_bin / f"pueue{ext}").exists():
        pueue_bin = str(kapsel_bin / f"pueue{ext}")
    if not pueued_bin and (kapsel_bin / f"pueued{ext}").exists():
        pueued_bin = str(kapsel_bin / f"pueued{ext}")

    return pueue_bin, pueued_bin


def _is_daemon_alive(pueue_bin: str) -> bool:
    """Checks if the Pueue daemon is running and responsive."""
    try:
        res = subprocess.run(
            [pueue_bin, "status", "--json"],
            capture_output=True,
            text=True,
            timeout=0.6,
        )
        return res.returncode == 0
    except Exception:
        return False


def _ensure_daemon_running(console: Optional[Console] = None, silent: bool = False) -> bool:
    """
    Ensures the Pueue daemon (pueued) is active.
    If not running, automatically starts 'pueued -d' in the background without user intervention.
    """
    pueue_bin, pueued_bin = _resolve_pueue_executables()
    if not pueue_bin:
        return False

    if _is_daemon_alive(pueue_bin):
        return True

    if not pueued_bin:
        return False

    con = console or Console(legacy_windows=False)
    if not silent:
        con.print("[dim]⚡ Autopilot: Starting Pueue background daemon...[/]")

    try:
        # Start daemon with -d flag
        subprocess.run(
            [pueued_bin, "-d"],
            capture_output=True,
            text=True,
            timeout=3.0,
        )
        # Wait up to 1.5 seconds for daemon to initialize socket
        for _ in range(15):
            time.sleep(0.1)
            if _is_daemon_alive(pueue_bin):
                if not silent:
                    con.print("[bold #10b981]✔ Pueue daemon is now active.[/]\n")
                return True
    except Exception:
        pass

    return _is_daemon_alive(pueue_bin)


class AutopilotPlugin(KapselPlugin):
    """
    Autopilot plugin integrating Pueue for background execution and queue management.
    All comments and descriptions are in English.
    """

    def __init__(self):
        super().__init__()
        self.pueue_bin: Optional[str] = None
        self.pueued_bin: Optional[str] = None

    @property
    def manifest(self) -> PluginManifest:
        return PluginManifest(
            id="autopilot",
            name="Autopilot",
            version="0.1.0",
            description="Autonomous background task queue and daemon execution manager powered by Pueue.",
            author="MrEiu",
            homepage="https://github.com/MrEiu/plugins",
        )

    def on_load(self, context: PluginContext) -> None:
        self.pueue_bin, self.pueued_bin = _resolve_pueue_executables()

        # Register 'auto' command into Kapsel Command Registry
        context.register_kps_command(
            name="auto",
            handler=self.handle_auto_command,
            help_text="Autonomous background task queue & process daemon manager (powered by Pueue)",
            subcommands={
                "add": "Enqueue a command for background execution (e.g. kps auto add npm run build)",
                "run": "Alias for add",
                "status": "Display full task queue status and concurrency limits",
                "log": "Display stdout/stderr output log for a specific task",
                "follow": "Stream real-time log output for a running task (tail -f style)",
                "pause": "Pause running tasks or entire task groups",
                "start": "Resume execution of paused tasks or groups",
                "restart": "Restart completed or failed task(s)",
                "kill": "Terminate running task(s) or whole groups",
                "clean": "Remove finished/successful tasks from queue history",
                "reset": "Kill all running tasks and reset entire queue",
                "parallel": "Adjust maximum concurrent worker tasks",
                "group": "Manage task groups and queues",
                "daemon": "Manage Pueue background service (status, start, stop, restart)",
            },
            usage="kps auto [add|status|log|follow|pause|start|kill|clean|daemon] [args...]",
            scope="feature",
        )

        # Register dynamic autocompletion hook
        context.register_hook(HookType.PROVIDE_COMPLETIONS, self.provide_completions)

    def on_unload(self) -> None:
        pass

    def handle_auto_command(self, args: List[str], console: Optional[Console] = None) -> int:
        """
        Dispatches 'kps auto' subcommands.
        """
        con = console or Console(legacy_windows=False)
        self.pueue_bin, self.pueued_bin = _resolve_pueue_executables()

        if not self.pueue_bin:
            con.print("\n[bold #f43f5e]Error:[/] [white]Pueue (pueue / pueued) is not installed on this system.[/]")
            con.print("[dim]Install automatically using:[/] [bold #00f0ff]kapsel add autopilot[/]\n")
            return 1

        # 1. Bare 'kps auto' or help flag -> Render interactive dashboard
        if not args or args[0] in ("-h", "--help", "help"):
            return self._render_dashboard(con)

        sub = args[0].lower()
        sub_args = args[1:]

        # 2. Daemon Management: 'kps auto daemon [status|start|stop|restart]'
        if sub == "daemon":
            return self._handle_daemon_subcommand(sub_args, con)

        # Ensure daemon is running for all operational tasks
        if not _ensure_daemon_running(con):
            con.print("[bold #f43f5e]Error:[/] [white]Failed to connect or start Pueue daemon (pueued).[/]")
            con.print("[dim]Try starting it manually with:[/] [bold #00f0ff]kps auto daemon start[/]\n")
            return 1

        # 3. Subcommand routing
        if sub in ("status", "st"):
            return self._handle_status(sub_args, con)
        elif sub in ("add", "run", "enqueue"):
            return self._handle_add(sub_args, con)
        elif sub in ("log", "logs"):
            return self._run_passthrough(["log"] + sub_args, con)
        elif sub in ("follow", "tail"):
            return self._run_passthrough(["follow"] + sub_args, con)
        elif sub == "pause":
            return self._run_passthrough(["pause"] + sub_args, con)
        elif sub in ("start", "resume"):
            return self._run_passthrough(["start"] + sub_args, con)
        elif sub in ("restart", "retry"):
            return self._run_passthrough(["restart"] + sub_args, con)
        elif sub in ("kill", "stop"):
            return self._run_passthrough(["kill"] + sub_args, con)
        elif sub in ("clean", "clear"):
            return self._run_passthrough(["clean"] + sub_args, con)
        elif sub == "reset":
            return self._run_passthrough(["reset"] + sub_args, con)
        elif sub in ("parallel", "concurrency"):
            return self._run_passthrough(["parallel"] + sub_args, con)
        elif sub == "group":
            return self._run_passthrough(["group"] + sub_args, con)
        elif sub == "wait":
            return self._run_passthrough(["wait"] + sub_args, con)
        else:
            # Natural command shortcut: if user enters 'kps auto <cmd...>' directly, treat as 'kps auto add'
            return self._handle_add(args, con)

    def _render_dashboard(self, con: Console) -> int:
        """Renders an informative, high-aesthetic status overview and cheat sheet."""
        daemon_alive = _is_daemon_alive(self.pueue_bin) if self.pueue_bin else False

        header_status = "[bold #10b981]🟢 Active (Running)[/]" if daemon_alive else "[bold #f43f5e]⚪ Inactive (Auto-starts on demand)[/]"

        con.print("\n[bold #00f0ff]🚀 Kapsel Autopilot[/] [dim]— Autonomous Task Queue & Daemon Manager (Pueue)[/]")
        con.print(f"[dim]Daemon Service:[/] {header_status}\n")

        # If daemon is alive, show a quick snapshot of active tasks
        if daemon_alive:
            self._render_task_summary(con)

        con.print("[bold white]Core Commands:[/]")
        con.print("  [bold #a855f7]kps auto add <command...>[/]      Enqueue background task (e.g. 'kps auto add cargo build')")
        con.print("  [bold #a855f7]kps auto status[/]                 View interactive queue status table")
        con.print("  [bold #a855f7]kps auto log [id][/]               Display full output logs for a task")
        con.print("  [bold #a855f7]kps auto follow [id][/]            Stream live real-time output (tail -f)")
        con.print("  [bold #a855f7]kps auto pause [id|group][/]       Pause active execution")
        con.print("  [bold #a855f7]kps auto start [id|group][/]       Resume queued or paused tasks")
        con.print("  [bold #a855f7]kps auto restart [id][/]           Re-run completed or failed tasks")
        con.print("  [bold #a855f7]kps auto kill [id][/]              Terminate a running task")
        con.print("  [bold #a855f7]kps auto clean[/]                  Remove all finished tasks from history")
        con.print("  [bold #a855f7]kps auto parallel <count>[/]       Set maximum concurrent tasks")
        con.print("  [bold #a855f7]kps auto daemon [status|start][/]  Inspect or control background daemon\n")
        return 0

    def _render_task_summary(self, con: Console) -> None:
        """Parses JSON from pueue status and renders task counts."""
        try:
            res = subprocess.run(
                [self.pueue_bin, "status", "--json"],
                capture_output=True,
                text=True,
                timeout=1.0,
            )
            if res.returncode == 0 and res.stdout.strip():
                data = json.loads(res.stdout)
                tasks: Dict[str, Any] = data.get("tasks", {})
                groups: Dict[str, Any] = data.get("groups", {})

                running_count = 0
                queued_count = 0
                done_count = 0
                failed_count = 0

                for t in tasks.values():
                    st = t.get("status", {})
                    if "Running" in st:
                        running_count += 1
                    elif "Queued" in st:
                        queued_count += 1
                    elif "Done" in st:
                        res_val = st["Done"].get("result")
                        if res_val == "Success":
                            done_count += 1
                        else:
                            failed_count += 1

                total = len(tasks)
                con.print(
                    Panel(
                        f"[white]Total Tasks:[/] [bold]{total}[/]  │  "
                        f"[bold #10b981]Running: {running_count}[/]  │  "
                        f"[bold #f59e0b]Queued: {queued_count}[/]  │  "
                        f"[bold #38bdf8]Done: {done_count}[/]  │  "
                        f"[bold #f43f5e]Failed: {failed_count}[/]",
                        title="[bold #00f0ff]📊 Task Queue Overview[/]",
                        border_style="#0891b2",
                        expand=False,
                    )
                )
        except Exception:
            pass

    def _handle_status(self, args: List[str], con: Console) -> int:
        """Displays status table or passes through raw JSON."""
        if "--json" in args or "-j" in args:
            return self._run_passthrough(["status"] + args, con)

        try:
            res = subprocess.run(
                [self.pueue_bin, "status", "--json"],
                capture_output=True,
                text=True,
                timeout=1.5,
            )
            if res.returncode != 0 or not res.stdout.strip():
                return self._run_passthrough(["status"], con)

            data = json.loads(res.stdout)
            tasks: Dict[str, Any] = data.get("tasks", {})
            groups: Dict[str, Any] = data.get("groups", {})

            if not tasks:
                con.print("\n[dim]Task queue is currently empty.[/]")
                con.print("[dim]Enqueue a new background task with:[/] [bold #00f0ff]kps auto add <command>[/]\n")
                return 0

            table = Table(
                title="[bold #00f0ff]🚀 Autopilot Task Queue[/]",
                border_style="#0891b2",
                header_style="bold #38bdf8",
                expand=False,
            )
            table.add_column("ID", justify="right", style="bold #a855f7")
            table.add_column("Status", justify="left")
            table.add_column("Command", justify="left", style="white")
            table.add_column("Group", justify="center", style="dim")
            table.add_column("Path", justify="left", style="dim")

            for tid, t in sorted(tasks.items(), key=lambda item: int(item[0])):
                st_obj = t.get("status", {})
                if "Running" in st_obj:
                    status_text = "[bold #10b981]🟢 Running[/]"
                elif "Queued" in st_obj:
                    status_text = "[bold #f59e0b]🟡 Queued[/]"
                elif "Paused" in st_obj:
                    status_text = "[bold #eab308]⏸️  Paused[/]"
                elif "Done" in st_obj:
                    res_val = st_obj["Done"].get("result")
                    if res_val == "Success":
                        status_text = "[bold #38bdf8]✔  Done[/]"
                    else:
                        status_text = f"[bold #f43f5e]❌ Failed ({res_val})[/]"
                else:
                    status_text = f"[dim]{list(st_obj.keys())[0] if st_obj else 'Unknown'}[/]"

                cmd_text = t.get("command", "")
                if len(cmd_text) > 50:
                    cmd_text = cmd_text[:47] + "..."

                grp = t.get("group", "default")
                p_str = t.get("path", "")
                if len(p_str) > 35:
                    p_str = "..." + p_str[-32:]

                table.add_row(str(tid), status_text, cmd_text, grp, p_str)

            con.print()
            con.print(table)
            con.print("\n[dim]Use 'kps auto log <id>' or 'kps auto follow <id>' to inspect output.[/]\n")
            return 0
        except Exception:
            return self._run_passthrough(["status"] + args, con)

    def _handle_add(self, args: List[str], con: Console) -> int:
        """Enqueues a task for execution."""
        if not args:
            con.print("[bold #f43f5e]Error:[/] Please specify a command to enqueue.")
            con.print("[dim]Usage:[/] [bold #00f0ff]kps auto add <command...>[/]\n")
            return 1

        # Check if user already provided '--'
        if "--" in args:
            cmd_args = ["add"] + args
        else:
            # Separate options from the command
            opts: List[str] = []
            cmd_parts: List[str] = []
            idx = 0
            while idx < len(args):
                arg = args[idx]
                if arg in ("-g", "--group", "-l", "--label", "-d", "--delay", "-p", "--priority"):
                    opts.append(arg)
                    if idx + 1 < len(args):
                        opts.append(args[idx + 1])
                        idx += 2
                        continue
                elif arg.startswith("-"):
                    opts.append(arg)
                else:
                    cmd_parts = args[idx:]
                    break
                idx += 1

            if not cmd_parts:
                cmd_parts = args

            cmd_args = ["add"] + opts + ["--"] + cmd_parts

        try:
            res = subprocess.run(
                [self.pueue_bin] + cmd_args,
                capture_output=True,
                text=True,
            )
            output = res.stdout.strip() or res.stderr.strip()
            if res.returncode == 0:
                con.print(f"[bold #10b981]✔ Task enqueued successfully.[/]")
                if output:
                    con.print(f"[dim]{output}[/]")
                con.print("[dim]View status with:[/] [bold #00f0ff]kps auto status[/]")
                con.print("[dim]Stream output with:[/] [bold #00f0ff]kps auto follow[/]\n")
                return 0
            else:
                con.print(f"[bold #f43f5e]Failed to enqueue task:[/] {output}")
                return res.returncode
        except Exception as e:
            con.print(f"[bold #f43f5e]Execution error:[/] {e}")
            return 1

    def _handle_daemon_subcommand(self, args: List[str], con: Console) -> int:
        """Handles daemon management subcommands."""
        action = args[0].lower() if args else "status"

        if action == "status":
            alive = _is_daemon_alive(self.pueue_bin) if self.pueue_bin else False
            if alive:
                con.print("[bold #10b981]🟢 Pueue daemon (pueued) is active and running.[/]")
            else:
                con.print("[yellow]⚪ Pueue daemon (pueued) is stopped.[/]")
                con.print("[dim]Start it with:[/] [bold #00f0ff]kps auto daemon start[/]")
            return 0

        elif action == "start":
            if _is_daemon_alive(self.pueue_bin):
                con.print("[dim]Pueue daemon is already running.[/]")
                return 0
            success = _ensure_daemon_running(con, silent=False)
            return 0 if success else 1

        elif action in ("stop", "shutdown"):
            if not _is_daemon_alive(self.pueue_bin):
                con.print("[dim]Pueue daemon is not running.[/]")
                return 0
            res = subprocess.run([self.pueue_bin, "shutdown"], capture_output=True, text=True)
            con.print(f"[bold #10b981]✔ Pueue daemon stopped.[/] [dim]{res.stdout.strip()}[/]")
            return res.returncode

        elif action == "restart":
            if _is_daemon_alive(self.pueue_bin):
                subprocess.run([self.pueue_bin, "shutdown"], capture_output=True, text=True)
                time.sleep(0.5)
            success = _ensure_daemon_running(con, silent=False)
            return 0 if success else 1

        else:
            con.print(f"[bold #f43f5e]Unknown daemon action:[/] '{action}' (options: status, start, stop, restart)")
            return 1

    def _run_passthrough(self, args: List[str], con: Console) -> int:
        """Executes pueue command with full terminal interactivity and streaming."""
        try:
            proc = subprocess.run([self.pueue_bin] + args)
            return proc.returncode
        except Exception as e:
            con.print(f"[bold #f43f5e]Error executing pueue {args[0]}:[/] {e}")
            return 1

    def provide_completions(self, text_before_cursor: str) -> List[Dict[str, Any]]:
        """
        Dynamically generates completions for 'kps auto' / 'kapsel auto'.
        Extracts subcommands and active task IDs from Pueue JSON.
        """
        command_line = text_before_cursor
        stripped = command_line.strip()
        tokens = stripped.split()
        if not tokens:
            return []

        # Check if line is targeting 'auto'
        first = tokens[0].lower()
        if first in ("kps", "kapsel") and len(tokens) >= 2 and tokens[1].lower() == "auto":
            auto_args = tokens[2:]
        elif first == "auto":
            auto_args = tokens[1:]
        else:
            return []

        # Dynamic completions for task IDs (e.g. 'kps auto log <Tab>', 'kps auto follow <Tab>', 'kps auto kill <Tab>')
        sub = auto_args[0].lower() if auto_args else ""
        if sub in ("log", "follow", "kill", "restart", "pause", "start", "tail") and (
            len(auto_args) == 1 and ends_with_space or len(auto_args) == 2 and not ends_with_space
        ):
            target_prefix = auto_args[1].lower() if len(auto_args) == 2 else ""
            return self._query_task_id_completions(target_prefix)

        # Case 3: Daemon subcommands ('kps auto daemon <Tab>')
        if sub == "daemon" and (
            len(auto_args) == 1 and ends_with_space or len(auto_args) == 2 and not ends_with_space
        ):
            d_prefix = auto_args[1].lower() if len(auto_args) == 2 else ""
            actions = [
                ("status", "Check if daemon is currently alive"),
                ("start", "Launch daemon in background"),
                ("stop", "Shut down daemon cleanly"),
                ("restart", "Restart daemon process"),
            ]
            return [
                {
                    "text": act,
                    "start_position": -len(d_prefix),
                    "display": act,
                    "display_meta": f"⚙️ {desc}",
                }
                for act, desc in actions
                if act.startswith(d_prefix)
            ]

        return []

    def _query_task_id_completions(self, prefix: str) -> List[Dict[str, Any]]:
        """Queries active and recent tasks from Pueue and yields task IDs with command preview."""
        self.pueue_bin, _ = _resolve_pueue_executables()
        if not self.pueue_bin or not _is_daemon_alive(self.pueue_bin):
            return []

        try:
            res = subprocess.run(
                [self.pueue_bin, "status", "--json"],
                capture_output=True,
                text=True,
                timeout=0.4,
            )
            if res.returncode != 0 or not res.stdout.strip():
                return []

            data = json.loads(res.stdout)
            tasks: Dict[str, Any] = data.get("tasks", {})
            results: List[Dict[str, Any]] = []

            for tid_str, t in sorted(tasks.items(), key=lambda item: int(item[0]), reverse=True):
                if not tid_str.startswith(prefix):
                    continue

                st_obj = t.get("status", {})
                if "Running" in st_obj:
                    icon = "🟢"
                elif "Queued" in st_obj:
                    icon = "🟡"
                elif "Paused" in st_obj:
                    icon = "⏸️"
                elif "Done" in st_obj:
                    icon = "✔" if st_obj["Done"].get("result") == "Success" else "❌"
                else:
                    icon = "📦"

                cmd = t.get("command", "")
                cmd_snippet = cmd[:30] + ("..." if len(cmd) > 30 else "")
                results.append({
                    "text": tid_str,
                    "start_position": -len(prefix),
                    "display": f"Task #{tid_str}",
                    "display_meta": f"{icon} {cmd_snippet}",
                })

            return results
        except Exception:
            return []
