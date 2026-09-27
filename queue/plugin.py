"""
Queue (Background Task Queue & Autonomous Execution) Plugin for Kapsel.
Bridges Pueue (daemon and CLI) to provide zero-friction background task execution,
queue orchestration, live logging, and process lifecycle management.
Features environment resource redundancy probing (look), multi-GPU {gpu} parameter matching,
bracket-based condition/command entry, and autonomous task dispatching.
All comments and descriptions are in English.
"""

import datetime
import json
import os
from pathlib import Path
import re
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

from .look import (
    render_look_dashboard,
    probe_all_gpus,
    probe_cpu,
    probe_memory,
    is_system_redundant,
)
from .scheduler import (
    add_pending_task,
    list_pending_tasks,
    remove_pending_task,
    get_max_running,
    set_max_running,
    get_check_interval,
    set_check_interval,
    get_active_allocated_gpus,
    get_thresholds,
    get_config,
    update_config,
    tick,
    load_state,
)

ensure_utf8_io()


def _resolve_pueue_executables() -> Tuple[Optional[str], Optional[str]]:
    """
    Locates 'pueue' (CLI client) and 'pueued' (daemon) executables:
    1. Local Kapsel bin directory (~/.kapsel/bin)
    2. Scoop direct app path and shims
    3. Cargo bin directory (~/.cargo/bin)
    4. WinGet links directory (Windows)
    5. System PATH
    """
    is_win = sys.platform == "win32"
    ext = ".exe" if is_win else ""

    pueue_bin: Optional[str] = None
    pueued_bin: Optional[str] = None

    user_home = Path.home()

    # 1. Local Kapsel bin directory
    kapsel_bin = get_kapsel_dir() / "bin"
    if (kapsel_bin / f"pueue{ext}").exists():
        pueue_bin = str(kapsel_bin / f"pueue{ext}")
    if (kapsel_bin / f"pueued{ext}").exists():
        pueued_bin = str(kapsel_bin / f"pueued{ext}")

    # 2. Direct Scoop app path & shims
    if not pueue_bin or not pueued_bin:
        scoop_current = user_home / "scoop" / "apps" / "pueue" / "current"
        if not pueue_bin and (scoop_current / f"pueue{ext}").exists():
            pueue_bin = str(scoop_current / f"pueue{ext}")
        if not pueued_bin and (scoop_current / f"pueued{ext}").exists():
            pueued_bin = str(scoop_current / f"pueued{ext}")

    # 3. Cargo bin directory
    if not pueue_bin or not pueued_bin:
        cargo_bin = user_home / ".cargo" / "bin"
        if not pueue_bin and (cargo_bin / f"pueue{ext}").exists():
            pueue_bin = str(cargo_bin / f"pueue{ext}")
        if not pueued_bin and (cargo_bin / f"pueued{ext}").exists():
            pueued_bin = str(cargo_bin / f"pueued{ext}")

    # 4. WinGet links
    if is_win and (not pueue_bin or not pueued_bin):
        winget_links = user_home / "AppData" / "Local" / "Microsoft" / "WinGet" / "Links"
        if not pueue_bin and (winget_links / f"pueue{ext}").exists():
            pueue_bin = str(winget_links / f"pueue{ext}")
        if not pueued_bin and (winget_links / f"pueued{ext}").exists():
            pueued_bin = str(winget_links / f"pueued{ext}")

    # 5. System PATH & Scoop shims
    if not pueue_bin:
        pueue_bin = shutil.which("pueue")
    if not pueued_bin:
        pueued_bin = shutil.which("pueued")

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
        con.print("[dim]⚡ Queue: Starting Pueue background daemon...[/]")

    try:
        is_win = sys.platform == "win32"
        if is_win:
            flags = 0
            if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
                flags |= subprocess.CREATE_NEW_PROCESS_GROUP
            if hasattr(subprocess, "DETACHED_PROCESS"):
                flags |= subprocess.DETACHED_PROCESS

            subprocess.Popen(
                [pueued_bin, "-d"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=flags,
                close_fds=True,
            )
        else:
            subprocess.Popen(
                [pueued_bin, "-d"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
            )

        # Wait up to 2.0 seconds for daemon to initialize socket
        for _ in range(20):
            time.sleep(0.1)
            if _is_daemon_alive(pueue_bin):
                if not silent:
                    con.print("[bold #10b981]✔ Pueue daemon is now active.[/]\n")
                return True
    except Exception:
        pass

    return _is_daemon_alive(pueue_bin)


def _ensure_scheduler_supervised(pueue_bin: str) -> None:
    """
    Ensures Pueue supervises the autonomous scheduler loop in the '_scheduler' group.
    Uses Pueue directly as the background supervisor without custom daemon code.
    """
    try:
        res = subprocess.run([pueue_bin, "status", "--json"], capture_output=True, text=True, timeout=1.0)
        if res.returncode != 0:
            return

        data = json.loads(res.stdout)
        groups = data.get("groups", {})
        if "_scheduler" not in groups:
            subprocess.run([pueue_bin, "group", "add", "_scheduler"], capture_output=True, timeout=2.0)
            subprocess.run([pueue_bin, "parallel", "-g", "_scheduler", "1"], capture_output=True, timeout=2.0)

        tasks = data.get("tasks", {})
        for t in tasks.values():
            if t.get("group") == "_scheduler" and t.get("status") in ("Running", "Queued"):
                return

        scheduler_script = Path(__file__).parent / "scheduler.py"
        py_exec = sys.executable
        subprocess.run(
            [pueue_bin, "add", "-g", "_scheduler", "--", py_exec, str(scheduler_script)],
            capture_output=True,
            timeout=2.0,
        )
    except Exception:
        pass


def _parse_pueue_iso(ts: Optional[str]) -> Optional[datetime.datetime]:
    """Parses Pueue ISO 8601 timestamps, sanitizing nanoseconds to 6 digits."""
    if not ts:
        return None
    ts_clean = re.sub(r'(\.\d{6})\d+', r'\1', str(ts))
    try:
        return datetime.datetime.fromisoformat(ts_clean)
    except Exception:
        return None


def _format_seconds(sec: float) -> str:
    """Formats duration in seconds to a human-readable string (e.g. '42.5s', '3m 12s')."""
    if sec < 60:
        return f"{sec:.1f}s"
    mins = int(sec // 60)
    rem_secs = sec % 60
    if mins < 60:
        return f"{mins}m {rem_secs:.0f}s"
    hours = int(mins // 60)
    rem_mins = mins % 60
    return f"{hours}h {rem_mins}m"


class QueuePlugin(KapselPlugin):
    """
    Queue plugin integrating Pueue for background execution, hardware resource redundancy probing,
    multi-GPU auto-dispatching with {gpu} matching, and queue lifecycle management.
    All comments and descriptions are in English.
    """

    def __init__(self):
        super().__init__()
        self.pueue_bin: Optional[str] = None
        self.pueued_bin: Optional[str] = None

    @property
    def manifest(self) -> PluginManifest:
        return PluginManifest(
            id="queue",
            name="Queue",
            version="0.1.7",
            description="Autonomous background task queue and resource-aware governor powered by Pueue with multi-GPU auto-dispatch.",
            author="MrEiu",
            homepage="https://github.com/MrEiu/plugins",
        )

    def on_load(self, context: PluginContext) -> None:
        self.pueue_bin, self.pueued_bin = _resolve_pueue_executables()

        # Register 'queue' command into Kapsel Command Registry
        context.register_kps_command(
            name="queue",
            handler=self.handle_queue_command,
            help_text="Autonomous task queue & resource-aware governor with multi-GPU auto-dispatch (powered by Pueue)",
            subcommands={
                "add": "Enqueue task with resource checking & {gpu} matching: kps queue add [condition] [command]",
                "look": "Inspect hardware resource redundancy (CPU, RAM, all GPUs VRAM & utilization)",
                "status": "Display active running tasks, allocated GPUs, and pending queue",
                "config": "View or adjust thresholds: kps queue config [--min-ram 1.0GB] [--min-vram 20%] [--limit 4]",
                "limit": "View or adjust maximum concurrent running tasks (default 4)",
                "interval": "View or adjust periodic scheduler check interval (default 5s)",
                "pending": "View and manage pending tasks waiting for resources",
                "log": "Display stdout/stderr output log for a specific task",
                "follow": "Stream real-time log output for a running task (tail -f style)",
                "pause": "Pause running tasks or entire task groups",
                "start": "Resume execution of paused tasks or groups",
                "restart": "Restart completed or failed task(s)",
                "kill": "Terminate running task(s) or whole groups",
                "clean": "Remove finished/successful tasks from queue history",
                "reset": "Kill all running tasks and reset entire queue",
                "parallel": "Adjust Pueue maximum concurrent worker tasks",
                "group": "Manage task groups and queues",
                "daemon": "Manage Pueue background service (status, start, stop, restart)",
            },
            usage="kps queue [add|look|status|config|limit|interval|pending|log|follow|pause|start|kill|clean|daemon] [args...]",
            scope="feature",
        )

        # Register dynamic autocompletion hook
        context.register_hook(HookType.PROVIDE_COMPLETIONS, self.provide_completions)

    def on_unload(self) -> None:
        pass

    def handle_queue_command(self, args: List[str], console: Optional[Console] = None) -> int:
        """
        Dispatches 'kps queue' subcommands.
        """
        con = console or Console(legacy_windows=False)
        self.pueue_bin, self.pueued_bin = _resolve_pueue_executables()

        if not self.pueue_bin:
            con.print("\n[bold #f43f5e]Error:[/] [white]Pueue (pueue / pueued) is not installed on this system.[/]")
            con.print("[dim]Install automatically using:[/] [bold #00f0ff]kapsel add queue[/]\n")
            return 1

        # 1. Bare 'kps queue' or help flag -> Render interactive dashboard
        if not args or args[0] in ("-h", "--help", "help"):
            return self._render_dashboard(con)

        sub = args[0].lower()
        sub_args = args[1:]

        # 2. Daemon Management: 'kps queue daemon [status|start|stop|restart]'
        if sub == "daemon":
            return self._handle_daemon_subcommand(sub_args, con)

        # Ensure Pueue daemon is running
        if not _ensure_daemon_running(con):
            con.print("[bold #f43f5e]Error:[/] [white]Failed to connect or start Pueue daemon (pueued).[/]")
            con.print("[dim]Try starting it manually with:[/] [bold #00f0ff]kps queue daemon start[/]\n")
            return 1

        # Ensure background scheduler is supervised by Pueue
        _ensure_scheduler_supervised(self.pueue_bin)

        # Execute instant scheduler tick for immediate responsiveness
        tick(self.pueue_bin)

        # 3. Subcommand routing
        if sub in ("look", "res", "resources", "probe"):
            return render_look_dashboard(
                con,
                allocated_gpus=get_active_allocated_gpus(),
                thresholds=get_thresholds(),
            )
        elif sub in ("config", "cfg", "settings", "threshold", "thresholds"):
            return self._handle_config(sub_args, con)
        elif sub in ("limit", "concurrency"):
            return self._handle_limit(sub_args, con)
        elif sub in ("interval", "tick"):
            return self._handle_interval(sub_args, con)
        elif sub in ("pending", "staged"):
            return self._handle_pending(sub_args, con)
        elif sub in ("status", "st"):
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
            return self._handle_clean(sub_args, con)
        elif sub == "reset":
            return self._run_passthrough(["reset"] + sub_args, con)
        elif sub in ("parallel",):
            return self._run_passthrough(["parallel"] + sub_args, con)
        elif sub == "group":
            return self._run_passthrough(["group"] + sub_args, con)
        elif sub == "wait":
            return self._run_passthrough(["wait"] + sub_args, con)
        else:
            # Shortcut: treat unknown command as 'add'
            return self._handle_add(args, con)

    handle_auto_command = handle_queue_command

    def _render_dashboard(self, con: Console) -> int:
        """Renders an informative status overview, hardware redundancy snapshot, and command guide."""
        daemon_alive = _is_daemon_alive(self.pueue_bin) if self.pueue_bin else False
        header_status = "[bold #10b981]🟢 Active (Running)[/]" if daemon_alive else "[bold #f43f5e]⚪ Inactive[/]"

        con.print("\n[bold #00f0ff]🚀 Kapsel Queue[/] [dim]— Resource-Aware Task Governor & Multi-GPU Scheduler[/]")
        con.print(f"[dim]Daemon Service:[/] {header_status}\n")

        if daemon_alive:
            self._render_task_summary(con)

        con.print("[bold white]Core Commands:[/]")
        con.print("  [bold #a855f7]kps queue look[/]                     Inspect hardware redundancy (CPU, RAM, GPUs)")
        con.print("  [bold #a855f7]kps queue config[/]                   View or adjust resource thresholds & limits")
        con.print("  [bold #a855f7]kps queue add [cmd][/]                 Enqueue task (default condition: look)")
        con.print("  [bold #a855f7]kps queue add [cond] [cmd][/]          Enqueue task with extra condition")
        con.print("  [bold #a855f7]kps queue add ... --gpu {gpu}[/]       Auto-match and allocate idle GPU (0, 1...)")
        con.print("  [bold #a855f7]kps queue status[/]                   View active execution & pending queue")
        con.print("  [bold #a855f7]kps queue limit [N][/]                 View or set max concurrent running tasks (default 4)")
        con.print("  [bold #a855f7]kps queue interval [N]s[/]             View or set scheduler polling interval")
        con.print("  [bold #a855f7]kps queue follow [id][/]              Stream live real-time output (tail -f)")
        con.print("  [bold #a855f7]kps queue log [id][/]                 Display output logs for a task")
        con.print("  [bold #a855f7]kps queue pause [id][/]               Pause active execution")
        con.print("  [bold #a855f7]kps queue start [id][/]               Resume paused task")
        con.print("  [bold #a855f7]kps queue kill [id][/]                Terminate a running task\n")
        return 0

    def _render_task_summary(self, con: Console) -> None:
        """Parses JSON from pueue status and renders summary."""
        try:
            res = subprocess.run([self.pueue_bin, "status", "--json"], capture_output=True, text=True, timeout=1.0)
            if res.returncode == 0 and res.stdout.strip():
                data = json.loads(res.stdout)
                tasks: Dict[str, Any] = data.get("tasks", {})

                running_count = 0
                queued_count = 0
                done_count = 0
                failed_count = 0

                for t in tasks.values():
                    if t.get("group") == "_scheduler":
                        continue
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

                pending_tasks = list_pending_tasks()
                pending_count = len(pending_tasks)
                max_run = get_max_running()

                # Hardware summary
                cpu = probe_cpu()
                mem = probe_memory()
                gpus = probe_all_gpus()
                gpu_summary = f"{len(gpus)} GPU(s)" if gpus else "No GPU"

                con.print(
                    Panel(
                        f"[white]Active Running:[/] [bold #10b981]{running_count} / {max_run} max[/]  │  "
                        f"[white]Pending in Staging:[/] [bold #f59e0b]{pending_count}[/]  │  "
                        f"[bold #38bdf8]Done: {done_count}[/]  │  "
                        f"[bold #f43f5e]Failed: {failed_count}[/]\n"
                        f"[dim]Environment:[/] CPU: {cpu['percent']:.0f}%  RAM Free: {mem['available_gb']:.1f}GB  GPUs: {gpu_summary}",
                        title="[bold #00f0ff]📊 Task Queue & Resource Governor Overview[/]",
                        border_style="#0891b2",
                        expand=False,
                    )
                )
        except Exception:
            pass

    def _handle_config(self, args: List[str], con: Console) -> int:
        """
        Views or updates queue scheduler configuration:
        - Max concurrency limit (e.g. 4)
        - Scheduler check interval (e.g. 5s)
        - Minimum free RAM threshold (supports numerical '1.0GB' or percentage '10%')
        - Minimum free GPU VRAM threshold (supports numerical '2.0GB' or percentage '20%')
        - Minimum free CPU threshold (supports '15%')
        """
        cfg = get_config()

        if not args:
            table = Table(
                title="[bold #00f0ff]⚙️ Kapsel Queue Scheduler Configuration[/]",
                border_style="#0891b2",
                header_style="bold #38bdf8",
                expand=False,
            )
            table.add_column("Parameter", style="bold #a855f7", no_wrap=True)
            table.add_column("Current Value", style="bold white")
            table.add_column("Description", style="dim")

            table.add_row(
                "max_running (limit)",
                str(cfg["max_running"]),
                "Maximum concurrent tasks executing simultaneously (default 4)",
            )
            table.add_row(
                "interval",
                f"{cfg['interval_seconds']}s",
                "Periodic scheduler check and polling interval (default 5s)",
            )
            table.add_row(
                "min_free_ram",
                str(cfg["min_free_ram"]),
                "Minimum system free RAM required (supports '1.0GB', '512MB', or '10%')",
            )
            table.add_row(
                "min_free_vram",
                str(cfg["min_free_vram"]),
                "Minimum GPU free VRAM required per card (supports '2.0GB' or '15%')",
            )
            table.add_row(
                "min_free_cpu",
                str(cfg["min_free_cpu"]),
                "Minimum idle CPU percentage required (default '15%')",
            )

            con.print()
            con.print(table)
            con.print("\n[bold white]Modify configuration examples:[/]")
            con.print("  [bold #00f0ff]kps queue config --min-ram 1.0GB[/]    (or '10%')")
            con.print("  [bold #00f0ff]kps queue config --min-vram 2.0GB[/]   (or '20%')")
            con.print("  [bold #00f0ff]kps queue config --min-cpu 10%[/]")
            con.print("  [bold #00f0ff]kps queue config --limit 4[/]")
            con.print("  [bold #00f0ff]kps queue config --interval 3s[/]\n")
            return 0

        # Parse key-value or flag arguments
        updates: Dict[str, Any] = {}
        idx = 0
        while idx < len(args):
            arg = args[idx]
            if arg.startswith("--"):
                key = arg[2:]
                if idx + 1 < len(args) and not args[idx + 1].startswith("--"):
                    updates[key] = args[idx + 1]
                    idx += 2
                    continue
                else:
                    con.print(f"[bold #f43f5e]Missing value for option:[/] {arg}")
                    return 1
            elif idx + 1 < len(args):
                updates[arg] = args[idx + 1]
                idx += 2
                continue
            else:
                con.print(f"[bold #f43f5e]Invalid configuration argument:[/] {arg}")
                return 1

        if updates:
            new_cfg = update_config(updates)
            con.print("[bold #10b981]✔ Scheduler configuration updated successfully:[/]")
            for k, v in updates.items():
                con.print(f"  [cyan]{k}:[/] [bold white]{v}[/]")
            tick(self.pueue_bin)
            return 0

        return 0

    def _handle_limit(self, args: List[str], con: Console) -> int:
        """Views or sets the maximum concurrent running task limit."""
        if not args:
            cur = get_max_running()
            con.print(f"[bold #00f0ff]Max Concurrency Limit:[/] [bold white]{cur}[/] [dim](default: 4)[/]")
            con.print("[dim]Set limit using:[/] [bold #a855f7]kps queue limit <count>[/]")
            return 0

        try:
            val = int(args[0])
            if val < 1:
                con.print("[bold #f43f5e]Error:[/] Limit must be at least 1.")
                return 1
            set_max_running(val)
            con.print(f"[bold #10b981]✔ Max concurrent running tasks set to:[/] [bold white]{val}[/]")
            # Immediately trigger tick with new limit
            tick(self.pueue_bin)
            return 0
        except ValueError:
            con.print(f"[bold #f43f5e]Invalid number:[/] '{args[0]}'")
            return 1

    def _handle_interval(self, args: List[str], con: Console) -> int:
        """Views or sets the periodic scheduler check interval."""
        if not args:
            cur = get_check_interval()
            con.print(f"[bold #00f0ff]Scheduler Polling Interval:[/] [bold white]{cur}s[/] [dim](default: 5s)[/]")
            con.print("[dim]Set interval using:[/] [bold #a855f7]kps queue interval <seconds>[/]")
            return 0

        try:
            val_str = args[0].lower().rstrip("s")
            val = int(val_str)
            if val < 1:
                con.print("[bold #f43f5e]Error:[/] Interval must be at least 1 second.")
                return 1
            set_check_interval(val)
            con.print(f"[bold #10b981]✔ Scheduler check interval set to:[/] [bold white]{val}s[/]")
            return 0
        except ValueError:
            con.print(f"[bold #f43f5e]Invalid seconds value:[/] '{args[0]}'")
            return 1

    def _handle_pending(self, args: List[str], con: Console) -> int:
        """Lists or removes tasks in the pending staging queue."""
        if args and args[0].lower() in ("rm", "remove", "del", "delete") and len(args) > 1:
            target_id = args[1]
            ok = remove_pending_task(target_id)
            if ok:
                con.print(f"[bold #10b981]✔ Removed pending task:[/] {target_id}")
            else:
                con.print(f"[bold #f43f5e]Pending task not found:[/] {target_id}")
            return 0

        pending_tasks = list_pending_tasks()
        if not pending_tasks:
            con.print("[dim]No tasks currently waiting in pending queue.[/]")
            return 0

        table = Table(
            title="[bold #f59e0b]⏳ Pending Tasks in Staging Queue[/]",
            border_style="#f59e0b",
            header_style="bold #38bdf8",
            expand=False,
        )
        table.add_column("Pending ID", justify="right", style="bold #a855f7")
        table.add_column("Command Template", justify="left", style="white")
        table.add_column("Extra Condition", justify="left", style="dim")
        table.add_column("Requires GPU", justify="center")

        for pt in pending_tasks:
            has_gpu = bool(re.search(r"\{gpu\}", pt.command_template, re.IGNORECASE))
            gpu_badge = "[bold #00f0ff]⚡ {gpu}[/]" if has_gpu else "[dim]CPU[/]"
            cond_display = pt.condition or "[dim](look default)[/]"
            table.add_row(pt.id, pt.command_template, cond_display, gpu_badge)

        con.print()
        con.print(table)
        con.print("[dim]Tasks will auto-dispatch when hardware resources, idle GPU, or conditions are met.[/]\n")
        return 0

    def _handle_add(self, args: List[str], con: Console) -> int:
        """
        Enqueues a task using bracket syntax or interactive prompt.
        Supports:
        - kps queue add [condition] [command]
        - kps queue add [command]
        - Interactive 2-step prompt if no arguments provided
        - Standard command fallback
        """
        command: Optional[str] = None
        condition: Optional[str] = None

        # 1. Bracket syntax detection (e.g. kps queue add [condition] [command])
        raw_args_line = " ".join(args).strip()
        brackets = re.findall(r"\[(.*?)\]", raw_args_line)

        if len(brackets) >= 2:
            condition = brackets[0].strip()
            command = brackets[1].strip()
        elif len(brackets) == 1:
            condition = None
            command = brackets[0].strip()
        elif not args:
            # 2. Interactive 2-Step Prompt
            con.print("\n[bold #00f0ff]⚡ Kapsel Queue · Task Enqueue Wizard[/]")
            con.print("[dim]Add a background command with resource checking & {gpu} matching (Ctrl+C to cancel)[/]\n")
            try:
                from prompt_toolkit import prompt

                # Step 1: Command
                command_in = prompt("Command to execute: ").strip()
                if not command_in:
                    con.print("[dim]Cancelled.[/]")
                    return 0
                command = command_in

                # Step 2: Extra condition
                cond_in = prompt("Extra condition (Optional, press Enter for default 'look' check): ").strip()
                condition = cond_in if cond_in else None
            except Exception:
                con.print("[bold #f43f5e]Interactive prompt interrupted.[/]")
                return 1
        else:
            # 3. Standard CLI flags or direct command line
            if "--if" in args:
                idx = args.index("--if")
                if idx + 1 < len(args):
                    condition = args[idx + 1]
                    cmd_parts = args[:idx] + args[idx + 2 :]
                    command = " ".join(cmd_parts).strip()
                else:
                    command = " ".join(args).strip()
            else:
                command = " ".join(args).strip()

        if not command:
            con.print("[bold #f43f5e]Error:[/] Command cannot be empty.")
            return 1

        # Enqueue into smart pending queue
        task = add_pending_task(command_template=command, condition=condition)

        # Trigger scheduler tick immediately
        dispatched = tick(self.pueue_bin)

        # Check if the newly added task was dispatched right away
        dispatched_this = [d for d in dispatched if d[0].id == task.id]
        if dispatched_this:
            dispatched_task, pueue_id = dispatched_this[0]
            gpu_msg = f" (Allocated GPU {dispatched_task.allocated_gpu})" if dispatched_task.allocated_gpu is not None else ""
            con.print(f"[bold #10b981]✔ Auto-dispatched task #{pueue_id}{gpu_msg}:[/] [white]{command}[/]")
            con.print("[dim]View live stream with:[/] [bold #00f0ff]kps queue follow[/]")
            con.print("[dim]Check status with:[/] [bold #00f0ff]kps queue status[/]\n")
        else:
            has_gpu = bool(re.search(r"\{gpu\}", command, re.IGNORECASE))
            reason = "Waiting for idle GPU" if has_gpu else "Waiting for resource redundancy / condition"
            con.print(f"[bold #f59e0b]⏳ Enqueued task [{task.id}] in Pending Staging Queue[/]")
            con.print(f"[dim]Command:[/] [white]{command}[/]")
            if condition:
                con.print(f"[dim]Condition:[/] [cyan]{condition}[/] + look")
            else:
                con.print("[dim]Condition:[/] look (CPU < 85%, RAM > 1.5GB, Idle GPU)")
            con.print(f"[dim]Status:[/] {reason}. Pueue scheduler will dispatch it automatically.\n")

        return 0

    def _handle_status(self, args: List[str], con: Console) -> int:
        """Displays full task status: resource overview, running tasks, and pending queue."""
        if "--json" in args or "-j" in args:
            return self._run_passthrough(["status"] + args, con)

        try:
            res = subprocess.run([self.pueue_bin, "status", "--json"], capture_output=True, text=True, timeout=1.5)
            if res.returncode != 0 or not res.stdout.strip():
                return self._run_passthrough(["status"], con)

            data = json.loads(res.stdout)
            tasks: Dict[str, Any] = data.get("tasks", {})
            sched_state = load_state()
            active_allocs = sched_state.get("active_allocations", {})

            # 1. Hardware Resource Summary bar
            cpu = probe_cpu()
            mem = probe_memory()
            gpus = probe_all_gpus()
            gpu_status_str = f"{len(gpus)} GPU(s)" if gpus else "No GPU"
            con.print(
                f"[dim]Resources:[/] CPU: [bold]{cpu['percent']:.1f}%[/] │ "
                f"RAM Free: [bold]{mem['available_gb']:.1f} GB[/] │ "
                f"GPUs: [bold]{gpu_status_str}[/] │ "
                f"Max Running: [bold]{get_max_running()}[/]"
            )

            # 2. Pueue Active Tasks Table
            active_tasks = {k: v for k, v in tasks.items() if v.get("group") != "_scheduler"}

            if active_tasks:
                table = Table(
                    title="[bold #00f0ff]🚀 Active Pueue Execution Queue[/]",
                    border_style="#0891b2",
                    header_style="bold #38bdf8",
                    expand=False,
                )
                table.add_column("ID", justify="right", style="bold #a855f7")
                table.add_column("Status", justify="left")
                table.add_column("GPU", justify="center")
                table.add_column("Command", justify="left", style="white")
                table.add_column("Group", justify="center", style="dim")

                for tid, t in sorted(active_tasks.items(), key=lambda item: int(item[0])):
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

                    # Check if this task was allocated a specific GPU
                    gpu_idx = active_allocs.get(str(tid))
                    gpu_badge = f"[bold #00f0ff]GPU {gpu_idx}[/]" if gpu_idx is not None else "[dim]-[/]"

                    cmd_text = t.get("command", "")
                    if len(cmd_text) > 55:
                        cmd_text = cmd_text[:52] + "..."

                    grp = t.get("group", "default")
                    table.add_row(str(tid), status_text, gpu_badge, cmd_text, grp)

                con.print()
                con.print(table)
            else:
                con.print("\n[dim]No active tasks executing in Pueue queue.[/]")

            # 3. Pending Staging Queue Table
            pending_tasks = list_pending_tasks()
            if pending_tasks:
                p_table = Table(
                    title="[bold #f59e0b]⏳ Pending Tasks Waiting for Hardware Resources / Idle GPU[/]",
                    border_style="#f59e0b",
                    header_style="bold #38bdf8",
                    expand=False,
                )
                p_table.add_column("Staging ID", justify="right", style="bold #a855f7")
                p_table.add_column("Command Template", justify="left", style="white")
                p_table.add_column("Condition", justify="left", style="dim")
                p_table.add_column("Requires GPU", justify="center")

                for pt in pending_tasks:
                    has_gpu = bool(re.search(r"\{gpu\}", pt.command_template, re.IGNORECASE))
                    gpu_badge = "[bold #00f0ff]⚡ {gpu}[/]" if has_gpu else "[dim]CPU[/]"
                    cond_str = pt.condition or "[dim](look)[/]"
                    p_table.add_row(pt.id, pt.command_template, cond_str, gpu_badge)

                con.print()
                con.print(p_table)

            con.print("\n[dim]Commands: 'kps queue look' (probe) │ 'kps queue follow <id>' │ 'kps queue log <id>'[/]\n")
            return 0
        except Exception:
            return self._run_passthrough(["status"] + args, con)

    def _handle_daemon_subcommand(self, args: List[str], con: Console) -> int:
        """Handles daemon management subcommands."""
        action = args[0].lower() if args else "status"

        if action == "status":
            alive = _is_daemon_alive(self.pueue_bin) if self.pueue_bin else False
            if alive:
                con.print("[bold #10b981]🟢 Pueue daemon (pueued) is active and running.[/]")
            else:
                con.print("[yellow]⚪ Pueue daemon (pueued) is stopped.[/]")
                con.print("[dim]Start it with:[/] [bold #00f0ff]kps queue daemon start[/]")
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

    def _handle_clean(self, args: List[str], con: Console) -> int:
        """
        Safely archives the complete queue status metadata, human-readable summary,
        and full per-task stdout/stderr output logs before executing 'pueue clean'.

        Archive Directory Structure:
            ~/.kapsel/queue/archives/YYYY-MM-DD_HHMMSS/
                ├── summary.log   (Human-readable overview table & error excerpts)
                ├── snapshot.json (Complete raw JSON metadata backup)
                └── logs/         (Individual task stdout/stderr console logs)
                    ├── task_1_npm-run-build_ok.log
                    └── ...
        """
        # 1. Fetch current status and full logs JSON from Pueue
        status_data: Dict[str, Any] = {}
        log_data: Dict[str, Any] = {}

        try:
            res_st = subprocess.run([self.pueue_bin, "status", "--json"], capture_output=True, text=True, timeout=2.0)
            if res_st.returncode == 0 and res_st.stdout.strip():
                status_data = json.loads(res_st.stdout)
        except Exception:
            pass

        try:
            res_log = subprocess.run([self.pueue_bin, "log", "--json"], capture_output=True, text=True, timeout=2.5)
            if res_log.returncode == 0 and res_log.stdout.strip():
                log_data = json.loads(res_log.stdout)
        except Exception:
            pass

        all_tasks: Dict[str, Any] = status_data.get("tasks", {})
        # Filter out internal supervisor task
        tasks_to_archive = {k: v for k, v in all_tasks.items() if v.get("group") != "_scheduler"}

        # Identify completed tasks eligible for cleanup
        done_tasks = {}
        for tid, t in tasks_to_archive.items():
            st = t.get("status", {})
            if "Done" in st:
                done_tasks[tid] = t

        now = datetime.datetime.now()
        timestamp_str = now.strftime("%Y-%m-%d_%H%M%S")
        archive_dir = get_kapsel_dir() / "queue" / "archives" / timestamp_str
        logs_dir = archive_dir / "logs"

        if done_tasks:
            try:
                logs_dir.mkdir(parents=True, exist_ok=True)

                # Step 1: Write raw snapshot.json
                snapshot_payload = {
                    "archived_at": now.isoformat(),
                    "clean_args": args,
                    "total_tasks_count": len(tasks_to_archive),
                    "done_tasks_count": len(done_tasks),
                    "tasks": tasks_to_archive,
                    "logs": log_data,
                }
                snapshot_file = archive_dir / "snapshot.json"
                snapshot_file.write_text(json.dumps(snapshot_payload, indent=2, ensure_ascii=False), encoding="utf-8")

                # Step 2: Build summary rows and write individual per-task logs in logs/
                summary_rows: List[Dict[str, str]] = []
                failed_details: List[Tuple[str, str, str, str]] = []

                for tid, t in sorted(tasks_to_archive.items(), key=lambda x: int(x[0])):
                    cmd = t.get("command") or t.get("original_command") or ""
                    path = t.get("path") or ""
                    group = t.get("group") or "default"
                    label = t.get("label") or "none"
                    st_obj = t.get("status", {})

                    status_str = "UNKNOWN"
                    exit_code = "-"
                    started_str = "-"
                    finished_str = "-"
                    duration_str = "-"
                    is_failed = False

                    if "Done" in st_obj:
                        done_info = st_obj["Done"]
                        res_val = done_info.get("result")
                        if res_val == "Success":
                            status_str = "SUCCESS"
                            exit_code = "0"
                        elif isinstance(res_val, dict) and "Failed" in res_val:
                            status_str = "FAILED"
                            exit_code = str(res_val["Failed"])
                            is_failed = True
                        elif res_val == "Killed":
                            status_str = "KILLED"
                            exit_code = "137"
                            is_failed = True
                        else:
                            status_str = str(res_val)
                            is_failed = True

                        start_dt = _parse_pueue_iso(done_info.get("start"))
                        end_dt = _parse_pueue_iso(done_info.get("end"))
                        if start_dt:
                            started_str = start_dt.strftime("%Y-%m-%d %H:%M:%S")
                        if end_dt:
                            finished_str = end_dt.strftime("%Y-%m-%d %H:%M:%S")
                        if start_dt and end_dt:
                            dur_sec = max(0.0, (end_dt - start_dt).total_seconds())
                            duration_str = _format_seconds(dur_sec)
                    elif "Running" in st_obj:
                        status_str = "RUNNING"
                        start_dt = _parse_pueue_iso(st_obj["Running"].get("start"))
                        if start_dt:
                            started_str = start_dt.strftime("%Y-%m-%d %H:%M:%S")
                    elif "Queued" in st_obj:
                        status_str = "QUEUED"
                    elif "Paused" in st_obj:
                        status_str = "PAUSED"

                    summary_rows.append({
                        "id": str(tid),
                        "status": status_str,
                        "exit": exit_code,
                        "duration": duration_str,
                        "started": started_str,
                        "finished": finished_str,
                        "command": cmd,
                    })

                    # Retrieve task stdout / stderr
                    task_log_obj = log_data.get(str(tid), {})
                    output_text = task_log_obj.get("output", "") if isinstance(task_log_obj, dict) else ""

                    # Sanitize command slug for clean filenames
                    clean_slug = re.sub(r'[^a-zA-Z0-9_\-\.]+', '_', cmd.strip())[:25].strip('_') or "cmd"
                    status_slug = "ok" if status_str == "SUCCESS" else status_str.lower()
                    task_filename = f"task_{tid}_{clean_slug}_{status_slug}.log"
                    task_log_path = logs_dir / task_filename

                    task_file_content = (
                        f"{'=' * 80}\n"
                        f"KAPSEL QUEUE TASK ARCHIVE - TASK #{tid}\n"
                        f"{'=' * 80}\n"
                        f"Command         : {cmd}\n"
                        f"Status          : {status_str} (Exit Code: {exit_code})\n"
                        f"Working Dir     : {path}\n"
                        f"Group / Label   : {group} / {label}\n"
                        f"Created At      : {t.get('created_at', '-')}\n"
                        f"Started At      : {started_str}\n"
                        f"Finished At     : {finished_str}\n"
                        f"Execution Time  : {duration_str}\n"
                        f"{'=' * 80}\n"
                        f"[STDOUT / STDERR CONSOLE OUTPUT]\n"
                        f"{'=' * 80}\n\n"
                        f"{output_text}\n"
                    )
                    task_log_path.write_text(task_file_content, encoding="utf-8")

                    if is_failed and output_text:
                        lines = output_text.strip().splitlines()
                        error_tail = "\n".join(lines[-15:]) if len(lines) > 15 else "\n".join(lines)
                        failed_details.append((str(tid), cmd, exit_code, error_tail))

                # Step 3: Write human-readable summary.log
                total_cnt = len(tasks_to_archive)
                success_cnt = sum(1 for r in summary_rows if r["status"] == "SUCCESS")
                failed_cnt = sum(1 for r in summary_rows if r["status"] in ("FAILED", "KILLED"))
                other_cnt = total_cnt - success_cnt - failed_cnt

                clean_cmd_str = f"kps queue clean {' '.join(args)}".strip()
                summary_lines = [
                    "=" * 80,
                    "KAPSEL QUEUE STATUS ARCHIVE",
                    f"Archive Time : {now.strftime('%Y-%m-%d %H:%M:%S')}",
                    f"Clean Command: {clean_cmd_str}",
                    f"Total Tasks  : {total_cnt} (Success: {success_cnt}, Failed: {failed_cnt}, Other: {other_cnt})",
                    "=" * 80,
                    "",
                    "[SUMMARY TABLE]",
                    f"{'ID':<6} {'STATUS':<10} {'EXIT':<6} {'DURATION':<12} {'STARTED':<20} {'FINISHED':<20} COMMAND",
                    "-" * 100,
                ]

                for r in summary_rows:
                    summary_lines.append(
                        f"#{r['id']:<5} {r['status']:<10} {r['exit']:<6} {r['duration']:<12} {r['started']:<20} {r['finished']:<20} {r['command']}"
                    )

                if failed_details:
                    summary_lines.extend([
                        "",
                        "=" * 80,
                        "[FAILED TASK ERROR SNIPPETS]",
                        "=" * 80,
                    ])
                    for tid, cmd, exit_code, err_snippet in failed_details:
                        summary_lines.extend([
                            f"\n--- Task #{tid} ({cmd}) [Exit Code: {exit_code}] ---",
                            err_snippet,
                        ])

                summary_lines.extend([
                    "",
                    "=" * 80,
                    "End of Archive",
                    "=" * 80,
                    "",
                ])

                summary_file = archive_dir / "summary.log"
                summary_file.write_text("\n".join(summary_lines), encoding="utf-8")

            except Exception as e:
                con.print(f"[bold #f59e0b]Warning:[/] Failed to write queue archive snapshot: {e}")

        # 2. Execute actual pueue clean
        clean_res = subprocess.run([self.pueue_bin, "clean"] + args, capture_output=True, text=True)
        if clean_res.returncode == 0:
            if done_tasks and archive_dir.exists():
                con.print(f"[bold #10b981]✔ Successfully cleaned {len(done_tasks)} completed task(s).[/]")
                con.print(f"[dim]📦 Full status & output archive saved to:[/] [bold #00f0ff]{archive_dir}[/]")
                con.print("  [dim]├── summary.log   (Human-readable summary table)[/]")
                con.print("  [dim]├── snapshot.json (Raw JSON metadata backup)[/]")
                con.print(f"  [dim]└── logs/         ({len(done_tasks)} task console output files)[/]\n")
            else:
                out_msg = clean_res.stdout.strip() or "No completed tasks to clean."
                con.print(f"[bold #10b981]✔ {out_msg}[/]\n")
            return 0
        else:
            err_msg = clean_res.stderr.strip() or clean_res.stdout.strip()
            con.print(f"[bold #f43f5e]Error cleaning queue:[/] {err_msg}\n")
            return clean_res.returncode

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
        Dynamically generates completions for 'kps queue'.
        Extracts subcommands and active task IDs from Pueue JSON.
        """
        command_line = text_before_cursor
        ends_with_space = command_line.endswith(" ")
        stripped = command_line.strip()
        tokens = stripped.split()
        if not tokens:
            return []

        first = tokens[0].lower()
        if first in ("kps", "kapsel") and len(tokens) >= 2 and tokens[1].lower() == "queue":
            queue_args = tokens[2:]
        elif first == "queue":
            queue_args = tokens[1:]
        else:
            return []

        # Case 1: Core Subcommands completion
        subcommands = [
            ("add", "Enqueue task with resource checking & {gpu} matching"),
            ("look", "Inspect hardware resource redundancy (CPU, RAM, GPUs)"),
            ("status", "Display full task queue status and pending tasks"),
            ("limit", "View or adjust maximum concurrent running tasks"),
            ("interval", "View or adjust periodic scheduler check interval"),
            ("pending", "View and manage tasks waiting in pending queue"),
            ("log", "Display output log for a specific task"),
            ("follow", "Stream real-time log output for a running task"),
            ("pause", "Pause running tasks or entire groups"),
            ("start", "Resume execution of paused tasks"),
            ("restart", "Restart completed or failed task(s)"),
            ("kill", "Terminate running task(s) or whole groups"),
            ("clean", "Remove finished/successful tasks from history"),
            ("reset", "Kill all running tasks and reset entire queue"),
            ("daemon", "Manage Pueue background service (status, start, stop)"),
        ]

        if not queue_args or (len(queue_args) == 1 and not ends_with_space):
            prefix = queue_args[0].lower() if queue_args else ""
            return [
                {
                    "text": name,
                    "start_position": -len(prefix),
                    "display": name,
                    "display_meta": f"🚀 {desc}",
                }
                for name, desc in subcommands
                if name.startswith(prefix)
            ]

        # Case 2: Dynamic completions for task IDs
        sub = queue_args[0].lower() if queue_args else ""
        if sub in ("log", "follow", "kill", "restart", "pause", "start", "tail") and (
            (len(queue_args) == 1 and ends_with_space) or (len(queue_args) == 2 and not ends_with_space)
        ):
            target_prefix = queue_args[1].lower() if len(queue_args) == 2 else ""
            return self._query_task_id_completions(target_prefix)

        # Case 3: Daemon subcommands
        if sub == "daemon" and (
            (len(queue_args) == 1 and ends_with_space) or (len(queue_args) == 2 and not ends_with_space)
        ):
            d_prefix = queue_args[1].lower() if len(queue_args) == 2 else ""
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
                if t.get("group") == "_scheduler":
                    continue
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


# Kapsel plugin export
Plugin = QueuePlugin
