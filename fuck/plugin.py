"""
Fuck (Command Auto-Correction) Plugin for Kapsel.
Bridges 'thefuck' to provide intelligent error correction and re-execution for console commands.
Exposes functional commands under the 'kps fuck' namespace.
All comments and descriptions are in English.
"""

import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
from typing import List, Optional

from rich.console import Console

from kapsel.core.executor import CommandExecutor
from kapsel.core.plugin.base import KapselPlugin, PluginManifest
from kapsel.core.plugin.context import PluginContext
from kapsel.storage.config import get_kapsel_dir
from kapsel.storage.history import HistoryManager
from kapsel.ui.banner import ensure_utf8_io

ensure_utf8_io()


def _is_thefuck_available() -> bool:
    """
    Checks if thefuck is installed and accessible:
    1. Direct Python module import (with imp shim)
    2. System PATH lookup (thefuck / thefuck.exe)
    3. Kapsel local bin directory (~/.kapsel/bin)
    """
    # 1. Check if thefuck package is installed in current Python environment
    try:
        import importlib.util

        if importlib.util.find_spec("thefuck") is not None:
            return True
    except Exception:
        pass

    # 2. Check system PATH
    if shutil.which("thefuck"):
        return True

    # 3. Check local Kapsel bin directory (~/.kapsel/bin/thefuck.cmd or thefuck)
    bin_dir = get_kapsel_dir() / "bin"
    is_win = sys.platform == "win32"
    local_launcher = bin_dir / ("thefuck.cmd" if is_win else "thefuck")
    if local_launcher.exists():
        return True

    return False


def _get_runner_script() -> Path:
    """Returns the path to the isolated runner script with Python 3.12+ compatibility."""
    return Path(__file__).parent / "runner.py"


class FuckPlugin(KapselPlugin):
    """
    Kapsel 'fuck' plugin integrating 'thefuck' command corrector.
    Provides automated correction of typos and command errors ('kps fuck', 'kps fuck -y', etc.).
    """

    manifest = PluginManifest(
        id="fuck",
        name="Fuck",
        version="0.1.0",
        description="Command auto-correction tool powered by thefuck.",
        author="Kapsel Team",
        homepage="https://github.com/MrEiu/plugins/tree/master/fuck",
        min_kapsel_version="0.1.0",
        dependencies=["thefuck"],
        tags=["correction", "thefuck", "terminal", "productivity", "tools"],
    )

    def on_load(self, context: PluginContext) -> None:
        """Registers the 'fuck' functional command under the 'kps' scope."""
        context.register_kps_command(
            name="fuck",
            handler=self.handle_fuck,
            help_text="Auto-correct previous console command using thefuck",
            usage="kps fuck [-y|--yes] [command...]",
            scope="feature",
        )

    def handle_fuck(self, args: List[str], console: Optional[Console] = None) -> int:
        """
        Dispatches 'kps fuck' command:
        - 'kps fuck'              -> Auto-corrects most recent command from history with interactive selection
        - 'kps fuck -y' / '--yes' -> Auto-corrects and runs immediately without confirmation
        - 'kps fuck <command...>' -> Auto-corrects the given command tokens
        - 'kps fuck --alias'      -> Displays shell alias configuration snippet
        - 'kps fuck --help'       -> Displays help documentation
        """
        con = console or Console(legacy_windows=False)

        # 1. Verify availability of thefuck
        if not _is_thefuck_available():
            con.print("[bold #f43f5e]Error:[/] [white]thefuck is not installed.[/]")
            con.print("[dim]To install thefuck automatically, run:[/] [bold #00f0ff]kapsel add fuck[/]\n")
            return 1

        # 2. Check for help requests
        if any(arg in ("-h", "--help", "help") for arg in args):
            con.print("\n[bold #00f0ff]● Kapsel Fuck Plugin (Command Auto-Correction)[/]")
            con.print("[dim]Powered by 'thefuck' (https://github.com/nvbn/thefuck)[/]\n")
            con.print("[bold white]Usage:[/]")
            con.print("  [bold #a855f7]kps fuck[/]                    Auto-correct and re-run previous failed command")
            con.print("  [bold #a855f7]kps fuck -y[/]                 Auto-correct and execute immediately (skip confirmation)")
            con.print("  [bold #a855f7]kps fuck --yes[/]              Alias for -y")
            con.print("  [bold #a855f7]kps fuck <command...>[/]       Fix specific command (e.g. 'kps fuck git br')")
            con.print("  [bold #a855f7]kps fuck --alias[/]            Show shell function integration snippet")
            con.print("  [bold #a855f7]kps fuck --version[/]          Show thefuck version information\n")
            return 0

        # 3. Check for version request
        if any(arg in ("-v", "--version") for arg in args):
            runner_py = _get_runner_script()
            res = subprocess.run([sys.executable, str(runner_py), "--version"])
            return res.returncode

        # 4. Check for alias request
        if any(arg in ("-a", "--alias") for arg in args):
            runner_py = _get_runner_script()
            res = subprocess.run([sys.executable, str(runner_py), "--alias"])
            return res.returncode

        # 5. Distinguish known thefuck flags from command tokens
        known_thefuck_flags = {
            "-y", "--yes", "--yeah", "--hard",
            "-r", "--repeat",
            "-d", "--debug",
            "--enable-experimental-instant-mode",
        }
        flags: List[str] = [arg for arg in args if arg in known_thefuck_flags]
        cmd_tokens: List[str] = [arg for arg in args if arg not in known_thefuck_flags]

        # 6. Resolve target command to fix
        target_tokens: List[str] = []
        hist_mgr = HistoryManager()
        recent_history = hist_mgr.get_recent_history_strings(limit=30)

        if cmd_tokens:
            # User provided an explicit command to fix (e.g. kps fuck git br)
            target_tokens = cmd_tokens
        else:
            # Look up the most recent command from SQLite history
            for entry in recent_history:
                cleaned = entry.strip()
                if not cleaned:
                    continue
                # Ignore previous fuck invocations and kapsel builtins
                parts = cleaned.split()
                primary = parts[0].lower() if parts else ""
                if primary in ("kps", "kapsel"):
                    if len(parts) > 1 and parts[1].lower() in ("fuck", "add", "rec", "profile", "alias"):
                        continue
                target_tokens = shlex.split(cleaned, posix=(sys.platform != "win32"))
                break

        if not target_tokens:
            con.print("[bold #f43f5e]Error:[/] [white]No previous command found in history to fix.[/]")
            con.print("[dim]You can provide a command directly: kps fuck <command>[/]\n")
            return 1

        # 7. Prepare execution environment (ensure TF_HISTORY is unset so known_args.command is used)
        env = os.environ.copy()
        env.pop("TF_HISTORY", None)
        env["TF_ALIAS"] = "fuck"
        env["PYTHONIOENCODING"] = "utf-8"

        # 8. Build runner arguments: flags + ['--'] + target_tokens
        runner_py = _get_runner_script()
        thefuck_args = [sys.executable, str(runner_py)] + flags + ["--"] + target_tokens

        try:
            # We connect stdin to sys.stdin so interactive arrow keys and Enter work.
            # stderr is left unpiped (None) so the interactive selection menu prints directly to terminal.
            # stdout is captured (PIPE) because thefuck prints the chosen command to stdout.
            proc = subprocess.Popen(
                thefuck_args,
                stdin=sys.stdin,
                stdout=subprocess.PIPE,
                stderr=None,
                env=env,
            )
            stdout_data, _ = proc.communicate()
        except KeyboardInterrupt:
            con.print("\n[dim]Aborted.[/]")
            return 130
        except Exception as e:
            con.print(f"[bold #f43f5e]Error running thefuck:[/] {e}")
            return 1

        if proc.returncode != 0:
            # thefuck exited with error or user cancelled (it already wrote message to stderr)
            return proc.returncode

        # 9. Read the chosen command and execute it via CommandExecutor
        chosen_command = stdout_data.decode("utf-8", errors="replace").strip()
        if not chosen_command:
            return 0

        con.print(f"[bold #00f0ff]➜[/] [white bold]{chosen_command}[/]")
        executor = CommandExecutor()
        summary = executor.execute(chosen_command)
        return summary.exit_code
