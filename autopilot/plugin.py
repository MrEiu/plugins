"""
Autopilot (PM2 Process Manager) Plugin for Kapsel.
Production process manager, cluster supervisor, and daemon orchestrator powered by PM2.
Exposes functional commands under 'kps autopilot' and 'kps ap'.
All comments and descriptions are in English.
"""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from kapsel.core.plugin.base import KapselPlugin, PluginManifest
from kapsel.core.plugin.context import PluginContext
from kapsel.core.plugin.hooks import HookType
from kapsel.ui.banner import ensure_utf8_io

ensure_utf8_io()


def _resolve_pm2_executable() -> Optional[str]:
    """
    Locates the PM2 executable across system PATH and known platform directories:
    1. System PATH ('pm2' or 'pm2.cmd' on Windows)
    2. Node/npm global directory (%APPDATA%\\npm\\pm2.cmd)
    3. Scoop shims (~/scoop/shims/pm2.cmd)
    4. PNPM / Yarn / Volta / FNM / NVM local binary paths
    5. Unix standard binary paths (/usr/local/bin/pm2, /opt/homebrew/bin/pm2)
    """
    # 1. System PATH
    bin_path = shutil.which("pm2")
    if bin_path:
        return bin_path

    is_win = sys.platform == "win32"
    if is_win:
        bin_path_cmd = shutil.which("pm2.cmd")
        if bin_path_cmd:
            return bin_path_cmd

        user_home = Path(os.environ.get("USERPROFILE", Path.home()))
        appdata = Path(os.environ.get("APPDATA", user_home / "AppData" / "Roaming"))
        localappdata = Path(os.environ.get("LOCALAPPDATA", user_home / "AppData" / "Local"))

        candidates = [
            appdata / "npm" / "pm2.cmd",
            appdata / "npm" / "pm2",
            user_home / "scoop" / "shims" / "pm2.cmd",
            user_home / "scoop" / "apps" / "pm2" / "current" / "pm2.cmd",
            localappdata / "pnpm" / "pm2.cmd",
            localappdata / "Yarn" / "bin" / "pm2.cmd",
            user_home / ".local" / "bin" / "pm2.cmd",
        ]
        for candidate in candidates:
            if candidate.exists():
                return str(candidate)
    else:
        user_home = Path(os.environ.get("HOME", Path.home()))
        candidates = [
            Path("/usr/local/bin/pm2"),
            Path("/opt/homebrew/bin/pm2"),
            user_home / ".local" / "share" / "pnpm" / "pm2",
            user_home / ".npm-global" / "bin" / "pm2",
            user_home / ".yarn" / "bin" / "pm2",
        ]
        for candidate in candidates:
            if candidate.exists() and candidate.is_file():
                return str(candidate)

    return None


def _format_bytes(num_bytes: int) -> str:
    """Formats bytes to human readable string (KB, MB, GB)."""
    if num_bytes < 1024:
        return f"{num_bytes} B"
    elif num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KB"
    elif num_bytes < 1024 * 1024 * 1024:
        return f"{num_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{num_bytes / (1024 * 1024 * 1024):.2f} GB"


def _format_uptime(uptime_ms: int) -> str:
    """Formats timestamp (epoch ms) to human readable uptime elapsed string."""
    if not uptime_ms or uptime_ms <= 0:
        return "-"
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    elapsed_sec = max(0, int((now_ms - uptime_ms) / 1000))
    if elapsed_sec < 60:
        return f"{elapsed_sec}s"
    elif elapsed_sec < 3600:
        return f"{elapsed_sec // 60}m {elapsed_sec % 60}s"
    elif elapsed_sec < 86400:
        return f"{elapsed_sec // 3600}h {(elapsed_sec % 3600) // 60}m"
    else:
        days = elapsed_sec // 86400
        hours = (elapsed_sec % 86400) // 3600
        return f"{days}d {hours}h"


class AutopilotPlugin(KapselPlugin):
    """
    PM2 Process Manager and Daemon Supervisor Plugin for Kapsel.
    Manages process lifecycles, cluster scaling, zero-downtime rolling reloads,
    and live telemetry monitoring.
    """

    def __init__(self):
        super().__init__(
            manifest=PluginManifest(
                id="autopilot",
                name="Autopilot",
                version="0.2.0",
                description="Production process manager and daemon supervisor powered by PM2.",
                author="MrEiu",
                dependencies=["rich>=13.0.0"],
                tags=["process", "daemon", "pm2", "cluster", "supervisor", "monitor"],
            )
        )
        self.pm2_bin: Optional[str] = None

    def on_load(self, context: PluginContext) -> None:
        self.pm2_bin = _resolve_pm2_executable()

        # Register 'autopilot' and short alias 'ap' into Kapsel Command Registry
        subcommands_meta = {
            "start": "Launch a script or binary (auto-detects Python, Bash, Node, TS, or binaries)",
            "stop": "Stop active process(es) gracefully (e.g. kps ap stop 0 or kps ap stop all)",
            "restart": "Restart process(es) (e.g. kps ap restart app)",
            "reload": "Perform zero-downtime rolling reload for cluster workers",
            "delete": "Stop and unregister process(es) from PM2 supervisor",
            "logs": "View or follow aggregated stdout/stderr logs",
            "follow": "Stream live real-time output log (tail -f style)",
            "flush": "Clear and truncate accumulated log files",
            "monit": "Launch PM2 full-screen interactive terminal monitor",
            "describe": "Inspect detailed process metadata, memory metrics, and environment",
            "save": "Freeze active process list to disk for reboot persistence",
            "resurrect": "Restore saved process snapshot after reboot",
            "startup": "Configure system boot auto-start service",
            "init": "Generate a production-ready ecosystem.config.cjs template",
            "status": "Show process status table or machine-readable JSON",
        }

        for cmd_name in ("autopilot", "ap"):
            context.register_kps_command(
                name=cmd_name,
                handler=self.handle_autopilot_command,
                help_text="Production process manager & daemon supervisor (powered by PM2)",
                subcommands=subcommands_meta,
                usage=f"kps {cmd_name} [start|stop|restart|reload|delete|logs|follow|monit|describe|save|resurrect|init|status] [args...]",
                scope="feature",
            )

        # Register dynamic autocompletion hook
        context.register_hook(HookType.PROVIDE_COMPLETIONS, self.provide_completions)

    def on_unload(self) -> None:
        pass

    def handle_autopilot_command(self, args: List[str], console: Optional[Console] = None) -> int:
        """
        Dispatches 'kps autopilot' / 'kps ap' subcommands.
        """
        con = console or Console(legacy_windows=False)
        if not self.pm2_bin:
            self.pm2_bin = _resolve_pm2_executable()

        if not self.pm2_bin:
            con.print("\n[bold #f43f5e]Error:[/] [white]PM2 is not installed or not found in system PATH.[/]")
            con.print("[dim]Install automatically using:[/] [bold #00f0ff]kapsel add autopilot[/]")
            con.print("[dim]Or install globally via npm:[/] [bold #00f0ff]npm install -g pm2[/]\n")
            return 1

        # 1. Bare command or help flags -> Render rich status dashboard
        if not args or args[0] in ("-h", "--help", "help"):
            return self._render_dashboard(con)

        sub = args[0].lower()
        sub_args = args[1:]

        # Subcommand dispatch
        if sub in ("status", "list", "ls"):
            return self._handle_status(sub_args, con)
        elif sub == "start":
            return self._handle_start(sub_args, con)
        elif sub == "stop":
            return self._run_pm2_cmd(["stop"] + sub_args, con)
        elif sub == "restart":
            return self._run_pm2_cmd(["restart"] + sub_args, con)
        elif sub == "reload":
            return self._run_pm2_cmd(["reload"] + sub_args, con)
        elif sub in ("delete", "del", "rm"):
            return self._run_pm2_cmd(["delete"] + sub_args, con)
        elif sub in ("logs", "log"):
            return self._handle_logs(sub_args, con)
        elif sub == "follow":
            return self._run_pm2_interactive(["logs"] + sub_args)
        elif sub == "flush":
            return self._run_pm2_cmd(["flush"] + sub_args, con)
        elif sub == "monit":
            return self._run_pm2_interactive(["monit"] + sub_args)
        elif sub in ("describe", "info", "show"):
            return self._run_pm2_cmd(["describe"] + sub_args, con)
        elif sub == "save":
            return self._run_pm2_cmd(["save"] + sub_args, con)
        elif sub == "resurrect":
            return self._run_pm2_cmd(["resurrect"] + sub_args, con)
        elif sub == "startup":
            return self._handle_startup(sub_args, con)
        elif sub == "init":
            return self._handle_init(sub_args, con)
        else:
            # If sub looks like a file to start (e.g. 'kps ap app.js'), treat as 'start'
            if Path(sub).exists() or sub.endswith((".js", ".ts", ".py", ".sh", ".json", ".cjs", ".mjs")):
                return self._handle_start([sub] + sub_args, con)
            return self._run_pm2_cmd(args, con)

    def _get_process_list(self) -> List[Dict[str, Any]]:
        """Queries 'pm2 jlist' to fetch active processes in structured JSON format."""
        if not self.pm2_bin:
            return []
        try:
            res = subprocess.run(
                [self.pm2_bin, "jlist"],
                capture_output=True,
                text=True,
                timeout=2.0,
            )
            if res.returncode == 0 and res.stdout.strip():
                return json.loads(res.stdout)
        except Exception:
            pass
        return []

    def _render_dashboard(self, con: Console) -> int:
        """Renders an aesthetic Cyberpunk/Neon Rich dashboard of PM2 managed processes."""
        procs = self._get_process_list()

        con.print()
        con.print(
            Panel(
                "[bold #00f0ff]✈️  Kapsel Autopilot Supervisor (Powered by PM2)[/]\n"
                "[dim white]Production process orchestrator with polyglot runtimes, cluster scaling, and zero-downtime rolling reload.[/]",
                border_style="#0891b2",
                expand=False,
            )
        )

        if not procs:
            con.print("[dim yellow]No processes currently registered with PM2.[/]")
            con.print("[dim]Start a process using:[/] [bold #00f0ff]kps ap start <script_or_config>[/]\n")
            self._print_quick_guide(con)
            return 0

        table = Table(
            title="[bold #38bdf8]Active Process Overview[/]",
            border_style="#0e7490",
            header_style="bold #00f0ff",
            show_lines=False,
        )
        table.add_column("ID", justify="right", style="cyan", width=4)
        table.add_column("Name", style="bold white", min_width=12)
        table.add_column("Mode", style="magenta", width=8)
        table.add_column("PID", justify="right", style="dim white", width=7)
        table.add_column("Status", justify="center", width=12)
        table.add_column("Restarts", justify="right", style="yellow", width=8)
        table.add_column("CPU", justify="right", width=7)
        table.add_column("Memory", justify="right", width=10)
        table.add_column("Uptime", justify="right", style="dim", width=10)

        online_count = 0
        stopped_count = 0
        errored_count = 0
        total_memory = 0

        for p in procs:
            pm_id = str(p.get("pm_id", "-"))
            name = str(p.get("name", "-"))
            pid = str(p.get("pid", "-"))
            monit = p.get("monit", {})
            cpu = monit.get("cpu", 0)
            mem_bytes = monit.get("memory", 0)
            total_memory += mem_bytes

            pm2_env = p.get("pm2_env", {})
            status = pm2_env.get("status", "unknown")
            exec_mode = pm2_env.get("exec_mode", "fork_mode")
            mode_display = "cluster" if "cluster" in exec_mode else "fork"
            restart_time = pm2_env.get("restart_time", 0)
            uptime_val = pm2_env.get("pm_uptime", 0)

            if status == "online":
                status_badge = "[bold #10b981]🟢 online[/]"
                online_count += 1
            elif status in ("stopping", "launching"):
                status_badge = "[bold #f59e0b]🟡 " + status + "[/]"
            elif status == "stopped":
                status_badge = "[dim white]⏸️  stopped[/]"
                stopped_count += 1
            elif status == "errored":
                status_badge = "[bold #f43f5e]🔴 errored[/]"
                errored_count += 1
            else:
                status_badge = f"[dim]{status}[/]"

            cpu_color = "#f43f5e" if cpu > 70 else ("#f59e0b" if cpu > 30 else "#10b981")
            cpu_display = f"[{cpu_color}]{cpu}%[/]"

            table.add_row(
                pm_id,
                name,
                mode_display,
                pid,
                status_badge,
                str(restart_time),
                cpu_display,
                _format_bytes(mem_bytes),
                _format_uptime(uptime_val),
            )

        con.print(table)

        # Summary footer bar
        con.print(
            Panel(
                f"[bold #10b981]Online: {online_count}[/]  │  "
                f"[dim white]Stopped: {stopped_count}[/]  │  "
                f"[bold #f43f5e]Errored: {errored_count}[/]  │  "
                f"[bold #38bdf8]Total Mem: {_format_bytes(total_memory)}[/]",
                title="[bold #00f0ff]📊 Resource Footprint[/]",
                border_style="#0891b2",
                expand=False,
            )
        )
        self._print_quick_guide(con)
        return 0

    def _print_quick_guide(self, con: Console) -> None:
        """Prints common command shortcuts."""
        con.print("[dim white]Common Commands:[/] [cyan]kps ap start <file>[/]  │  [cyan]kps ap stop <id|name>[/]  │  [cyan]kps ap reload <id>[/]")
        con.print("[dim white]Observability:  [/] [cyan]kps ap logs [id][/]       │  [cyan]kps ap monit[/]           │  [cyan]kps ap save[/]\n")

    def _handle_status(self, args: List[str], con: Console) -> int:
        """Handles 'status' or 'list' subcommand."""
        if "--json" in args or "-j" in args:
            procs = self._get_process_list()
            con.print_json(json.dumps(procs, indent=2))
            return 0
        return self._render_dashboard(con)

    def _handle_start(self, args: List[str], con: Console) -> int:
        """
        Launches a target script or configuration with smart runtime inference:
        - .py: automatically appends '--interpreter python'
        - .sh / .bash: automatically appends '--interpreter bash'
        - .ts: automatically appends '--interpreter tsx' or 'ts-node'
        """
        if not args:
            con.print("[bold #f43f5e]Error:[/] [white]Missing script, binary, or configuration file to start.[/]")
            con.print("[dim]Example:[/] [bold #00f0ff]kps ap start app.js --name my-server[/]")
            return 1

        target = args[0]
        extra_args = args[1:]
        cmd = ["start", target]

        # Automatic polyglot runtime inference if --interpreter is not already specified
        has_interpreter = any(arg.startswith("--interpreter") for arg in extra_args)
        if not has_interpreter:
            target_lower = target.lower()
            if target_lower.endswith(".py"):
                # Detect python executable
                py_bin = sys.executable if sys.executable else "python"
                cmd.extend(["--interpreter", py_bin])
            elif target_lower.endswith((".sh", ".bash")):
                cmd.extend(["--interpreter", "bash"])
            elif target_lower.endswith(".ts"):
                if shutil.which("tsx"):
                    cmd.extend(["--interpreter", "tsx"])
                elif shutil.which("ts-node"):
                    cmd.extend(["--interpreter", "ts-node"])
                elif shutil.which("bun"):
                    cmd.extend(["--interpreter", "bun"])

        cmd.extend(extra_args)
        return self._run_pm2_cmd(cmd, con)

    def _handle_logs(self, args: List[str], con: Console) -> int:
        """Displays or streams process logs."""
        return self._run_pm2_interactive(["logs"] + args)

    def _handle_startup(self, args: List[str], con: Console) -> int:
        """Configures system boot auto-start for PM2."""
        con.print("[bold #00f0ff]🚀 Configuring PM2 System Startup Service...[/]")
        is_win = sys.platform == "win32"
        if is_win:
            con.print("[white]On Windows, PM2 can be registered as a Windows Service or via Task Scheduler.[/]")
            con.print("[dim]Option 1 (Recommended):[/] [cyan]npm install -g pm2-windows-service && pm2-service-install[/]")
            con.print("[dim]Option 2 (Task Scheduler):[/] [cyan]pm2 save[/] [dim]then add 'pm2 resurrect' on user logon.[/]")
            return 0
        else:
            return self._run_pm2_cmd(["startup"] + args, con)

    def _handle_init(self, args: List[str], con: Console) -> int:
        """Generates a modern, production-ready ecosystem.config.cjs template."""
        target_path = Path.cwd() / "ecosystem.config.cjs"
        if target_path.exists():
            con.print(f"[yellow]Notice:[/] File already exists at [bold]{target_path}[/]")
            return 0

        template_content = """module.exports = {
  apps: [
    {
      name: 'api-server',
      script: './src/index.js',
      instances: 'max',
      exec_mode: 'cluster',
      autorestart: true,
      watch: false,
      max_memory_restart: '300M',
      env: {
        NODE_ENV: 'development',
        PORT: 3000,
      },
      env_production: {
        NODE_ENV: 'production',
        PORT: 8080,
      },
    },
    {
      name: 'background-worker',
      script: './scripts/worker.py',
      interpreter: 'python',
      autorestart: true,
      restart_delay: 3000,
      env: {
        PYTHONUNBUFFERED: '1',
      },
    },
  ],
};
"""
        target_path.write_text(template_content, encoding="utf-8")
        con.print(f"[bold #10b981]✔ Created modern PM2 ecosystem template at:[/] [white]{target_path}[/]")
        con.print("[dim]Start all configured services with:[/] [bold #00f0ff]kps ap start ecosystem.config.cjs[/]")
        return 0

    def _run_pm2_cmd(self, args: List[str], con: Console) -> int:
        """Executes a non-interactive PM2 command and formats output."""
        if not self.pm2_bin:
            return 1
        try:
            res = subprocess.run([self.pm2_bin] + args, capture_output=True, text=True, timeout=30)
            if res.stdout:
                con.print(res.stdout.strip())
            if res.stderr and res.returncode != 0:
                con.print(f"[bold #f43f5e]{res.stderr.strip()}[/]")
            return res.returncode
        except subprocess.TimeoutExpired:
            con.print("[bold #f43f5e]PM2 command timed out after 30 seconds.[/]")
            return 124
        except Exception as e:
            con.print(f"[bold #f43f5e]Failed to execute PM2 command: {e}[/]")
            return 1

    def _run_pm2_interactive(self, args: List[str]) -> int:
        """Executes an interactive or streaming PM2 command directly attached to TTY."""
        if not self.pm2_bin:
            return 1
        try:
            return subprocess.call([self.pm2_bin] + args)
        except KeyboardInterrupt:
            return 0
        except Exception as e:
            print(f"Error running PM2: {e}", file=sys.stderr)
            return 1

    def provide_completions(self, text: str) -> List[Dict[str, Any]]:
        """
        Dynamically generates Carapace completions for 'kps ap' and 'kps autopilot':
        - Subcommands: start, stop, restart, reload, delete, logs, follow, monit, describe, save, etc.
        - Process Targets: queries 'pm2 jlist' (0.4s timeout) and yields live process names and IDs
          enriched with status badges (🟢/🔴/⏸️), PID, CPU%, and Memory usage.
        """
        stripped = text.strip()
        ends_with_space = text.endswith(" ")
        tokens = stripped.split()

        if not tokens:
            return []

        root_cmd = tokens[0].lower()
        if root_cmd not in ("kps", "kapsel"):
            return []

        if len(tokens) < 2:
            return []

        plugin_token = tokens[1].lower()
        if plugin_token not in ("autopilot", "ap"):
            return []

        args = tokens[2:]

        # Case 1: Subcommand completion ('kps ap <Tab>')
        if not args or (len(args) == 1 and not ends_with_space):
            prefix = args[0].lower() if args else ""
            subcommands = [
                ("start", "Launch script, binary, or ecosystem config"),
                ("stop", "Stop active process gracefully"),
                ("restart", "Kill and restart process"),
                ("reload", "Zero-downtime rolling reload for cluster"),
                ("delete", "Unregister process from PM2"),
                ("logs", "View aggregated output logs"),
                ("follow", "Stream live real-time output log"),
                ("flush", "Clear and truncate accumulated log files"),
                ("monit", "Open interactive terminal monitor"),
                ("describe", "Inspect detailed process metadata"),
                ("save", "Freeze process list to disk for reboot"),
                ("resurrect", "Restore saved process snapshot"),
                ("startup", "Configure system boot auto-start"),
                ("init", "Generate ecosystem.config.cjs template"),
                ("status", "Show process overview table or JSON"),
            ]
            return [
                {
                    "text": cmd,
                    "start_position": -len(prefix),
                    "display": cmd,
                    "display_meta": f"🚀 {desc}",
                }
                for cmd, desc in subcommands
                if cmd.startswith(prefix)
            ]

        # Case 2: Process name & ID completion ('kps ap stop <Tab>', 'kps ap logs <Tab>', etc.)
        sub = args[0].lower()
        if sub in ("stop", "restart", "reload", "delete", "del", "rm", "logs", "log", "follow", "flush", "describe", "info", "show"):
            if (len(args) == 1 and ends_with_space) or (len(args) == 2 and not ends_with_space):
                prefix = args[1].lower() if len(args) == 2 else ""
                return self._query_process_completions(prefix)

        return []

    def _query_process_completions(self, prefix: str) -> List[Dict[str, Any]]:
        """Queries 'pm2 jlist' with a strict 0.4s timeout and yields dynamic completion items."""
        pm2_bin = self.pm2_bin or _resolve_pm2_executable()
        if not pm2_bin:
            return []

        try:
            res = subprocess.run(
                [pm2_bin, "jlist"],
                capture_output=True,
                text=True,
                timeout=0.4,
            )
            if res.returncode != 0 or not res.stdout.strip():
                return []

            procs = json.loads(res.stdout)
            results: List[Dict[str, Any]] = []

            # Include 'all' shortcut if prefix matches
            if "all".startswith(prefix):
                results.append({
                    "text": "all",
                    "start_position": -len(prefix),
                    "display": "all",
                    "display_meta": "⚡ Apply to all managed processes",
                })

            for p in procs:
                pm_id = str(p.get("pm_id", ""))
                name = str(p.get("name", ""))
                monit = p.get("monit", {})
                cpu = monit.get("cpu", 0)
                mem = monit.get("memory", 0)
                pm2_env = p.get("pm2_env", {})
                status = pm2_env.get("status", "unknown")

                icon = "🟢" if status == "online" else ("🔴" if status == "errored" else "⏸️")
                meta_str = f"{icon} {status} | CPU: {cpu}% | Mem: {_format_bytes(mem)}"

                # Match against process name
                if name.lower().startswith(prefix):
                    results.append({
                        "text": name,
                        "start_position": -len(prefix),
                        "display": f"{name} (#{pm_id})",
                        "display_meta": meta_str,
                    })

                # Match against process ID
                if pm_id.startswith(prefix) and pm_id != name:
                    results.append({
                        "text": pm_id,
                        "start_position": -len(prefix),
                        "display": f"#{pm_id} ({name})",
                        "display_meta": meta_str,
                    })

            return results
        except Exception:
            return []


Plugin = AutopilotPlugin
