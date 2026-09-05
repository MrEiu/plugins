"""
Portal (Directory Teleportation) Plugin for Kapsel.
Bridges 'zoxide' to provide intelligent, frecency-based directory navigation
and workspace jumping across all host operating systems.
Exposes functional commands under 'kps portal', 'portal', and 'z'.
All comments and descriptions are in English.
"""

import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
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


def _resolve_zoxide_executable() -> Optional[str]:
    """
    Locates the zoxide executable across known system and sandbox paths:
    1. System PATH
    2. Local Kapsel bin directory (~/.kapsel/bin/zoxide.exe or zoxide)
    3. Scoop shims and apps directory
    4. WinGet links directory
    5. Cargo bin directory (~/.cargo/bin)
    6. Common Unix locations (/usr/local/bin, /opt/homebrew/bin, ~/.local/bin)
    """
    # 1. System PATH
    p = shutil.which("zoxide")
    if p:
        return p

    is_win = sys.platform == "win32"
    exe_name = "zoxide.exe" if is_win else "zoxide"

    # 2. Local Kapsel bin directory
    local_bin = get_kapsel_dir() / "bin" / exe_name
    if local_bin.exists():
        return str(local_bin)

    user_home = Path(os.environ.get("USERPROFILE" if is_win else "HOME", Path.home()))

    # 3. Windows specific candidate directories
    if is_win:
        candidates = [
            user_home / "scoop" / "shims" / exe_name,
            user_home / "scoop" / "apps" / "zoxide" / "current" / exe_name,
            user_home / "AppData" / "Local" / "Microsoft" / "WinGet" / "Links" / exe_name,
            user_home / ".cargo" / "bin" / exe_name,
            user_home / ".local" / "bin" / exe_name,
        ]
        for candidate in candidates:
            if candidate.exists():
                return str(candidate)
    else:
        # 4. Unix specific candidate directories
        unix_candidates = [
            Path("/opt/homebrew/bin") / exe_name,
            Path("/usr/local/bin") / exe_name,
            Path("/usr/bin") / exe_name,
            user_home / ".cargo" / "bin" / exe_name,
            user_home / ".local" / "bin" / exe_name,
            user_home / ".nix-profile" / "bin" / exe_name,
        ]
        for candidate in unix_candidates:
            if candidate.exists():
                return str(candidate)

    return None


class PortalPlugin(KapselPlugin):
    """
    Kapsel Portal Plugin: Smart Directory Teleportation powered by zoxide.
    Enables instant jumping via 'z <query>', 'portal <query>', and 'kps portal'.
    """

    manifest = PluginManifest(
        id="portal",
        name="Portal",
        version="0.1.0",
        description="Smart directory teleportation and workspace navigator powered by zoxide.",
        author="Kapsel Team",
        homepage="https://github.com/MrEiu/plugins/tree/master/portal",
        min_kapsel_version="0.1.0",
        tags=["zoxide", "cd", "navigation", "portal", "frecency", "workspace"],
    )

    def __init__(self) -> None:
        super().__init__()
        self.context: Optional[PluginContext] = None
        self._zoxide_bin: Optional[str] = None
        self._last_recorded_cwd: Optional[str] = None
        self._cached_recent_dirs: List[str] = []
        self._cache_lock = threading.Lock()

    def on_load(self, context: PluginContext) -> None:
        self.context = context
        self._zoxide_bin = _resolve_zoxide_executable()

        # 1. Pre-execution filter: intercepts 'z <query>' and 'portal <query>'
        context.register_hook(HookType.FILTER_COMMAND, self.filter_command)

        # 2. Command execution tracking: auto-learns visited directories
        context.register_hook(HookType.ON_AFTER_EXECUTE, self.on_after_execute)

        # 3. Dynamic autocompletion for portal and zoxide paths
        context.register_hook(HookType.PROVIDE_COMPLETIONS, self.provide_completions)

        # 4. Register functional management command: 'kps portal'
        context.register_kps_command(
            name="portal",
            handler=self.handle_portal,
            help_text="Smart directory teleportation and workspace navigator powered by zoxide",
            usage="kps portal [ls|add|rm|query|open|doctor|init] [keywords]",
            scope="feature",
        )

        # Initial background directory record
        try:
            self._async_add_directory(str(Path.cwd()))
        except Exception:
            pass

    def filter_command(self, raw_command: str) -> Tuple[bool, str]:
        """
        Translates 'z <query>' and 'portal <query>' directly into shell directory changes.
        Returns (is_handled, transformed_command).
        """
        stripped = raw_command.strip()
        if not stripped:
            return False, raw_command

        tokens = stripped.split(maxsplit=1)
        prefix = tokens[0].lower()

        # Only intercept 'z' and 'portal' as standalone prefixes
        if prefix not in ("z", "portal"):
            return False, raw_command

        # If zoxide is not available on host, do not intercept
        if not self._zoxide_bin:
            return False, raw_command

        query = tokens[1].strip() if len(tokens) > 1 else ""

        # Handle bare 'z' or 'portal' -> jump to home directory (standard cd behavior)
        if not query:
            return True, "cd ~"

        # Special directory tokens
        if query in ("-", "..", "/", "\\", "~"):
            return True, f"cd {query}"

        # If direct relative or absolute path exists, jump and record
        query_path = Path(query).expanduser()
        if query_path.exists() and query_path.is_dir():
            resolved = str(query_path.resolve())
            self._async_add_directory(resolved)
            return True, f'cd "{resolved}"'

        # Query zoxide for the best matching directory
        matched = self._query_zoxide_best(query)
        if matched:
            self._async_add_directory(matched)
            return True, f'cd "{matched}"'

        # No match found: output warning in terminal and don't execute a broken command
        con = Console(legacy_windows=False)
        con.print(f"[bold #f43f5e]portal:[/] No matching directory found for '[white]{query}[/]' in database.")
        con.print("[dim]Tip: Use 'kps portal ls' to view registered paths or 'kps portal add <path>' to register.[/]\n")
        return True, ""

    def on_after_execute(self, command: str, exit_code: int, duration_ms: float) -> None:
        """
        Triggered after every command execution in Kapsel.
        Automatically updates zoxide frecency ranking if the working directory changed.
        """
        if exit_code != 0:
            return

        try:
            current_cwd = str(Path.cwd().resolve())
            if current_cwd != self._last_recorded_cwd:
                self._last_recorded_cwd = current_cwd
                self._async_add_directory(current_cwd)
        except Exception:
            pass

    def provide_completions(self, text_before_cursor: str) -> List[dict]:
        """
        Injects directory candidates into Kapsel prompt completions.
        Triggered when typing 'kps portal ', 'portal ', or 'z '.
        """
        stripped = text_before_cursor.lstrip()
        matched_prefix = None
        for p in ("kps portal ", "kapsel portal ", "portal ", "z "):
            if stripped.startswith(p):
                matched_prefix = p
                break

        if not matched_prefix:
            return []

        if not self._zoxide_bin:
            return []

        partial = stripped[len(matched_prefix):].strip()
        entries = self._list_zoxide_entries(partial)

        candidates = []
        for path_str in entries[:15]:
            path_obj = Path(path_str)
            basename = path_obj.name or path_str
            candidates.append({
                "text": basename,
                "display": f"{basename}  [dim]({path_str})[/]",
                "display_meta": "[portal]",
            })
        return candidates

    def handle_portal(self, args: List[str], console: Optional[Console] = None) -> int:
        """Main command handler for 'kps portal'."""
        con = console or Console(legacy_windows=False)

        # Ensure zoxide binary is available
        if not self._zoxide_bin:
            self._zoxide_bin = _resolve_zoxide_executable()

        if not self._zoxide_bin:
            con.print("[bold #f43f5e]Error:[/] 'zoxide' is not installed or not found on PATH.")
            con.print("[dim]Run 'kps add portal' or install zoxide via 'scoop install zoxide' / 'winget install ajeetdsouza.zoxide'.[/]\n")
            return 1

        if not args or args[0] in ("-h", "--help", "help"):
            self._render_help(con)
            return 0

        subcmd = args[0].lower()

        if subcmd in ("ls", "list"):
            return self._handle_list(args[1:], con)
        elif subcmd in ("add", "+"):
            return self._handle_add(args[1:], con)
        elif subcmd in ("rm", "remove", "-"):
            return self._handle_remove(args[1:], con)
        elif subcmd == "query":
            return self._handle_query(args[1:], con)
        elif subcmd in ("open", "explore"):
            return self._handle_open(args[1:], con)
        elif subcmd == "doctor":
            return self._handle_doctor(con)
        elif subcmd == "edit":
            return self._run_zoxide_interactive(["edit"])
        elif subcmd == "init":
            return self._handle_init_script(args[1:], con)
        else:
            # Direct query jump or output: 'kps portal <keywords>'
            query_str = " ".join(args)
            matched = self._query_zoxide_best(query_str)
            if matched:
                if os.environ.get("KAPSEL_ACTIVE") == "1":
                    try:
                        os.chdir(matched)
                        self._async_add_directory(matched)
                        con.print(f"[bold #10b981]✔ Teleported to:[/] [bold #00f0ff]{matched}[/]")
                        return 0
                    except Exception as e:
                        con.print(f"[bold #f43f5e]Failed to change directory:[/] {e}")
                        return 1
                else:
                    # In external shell: print path to stdout so it can be used with cd $(kps portal <query>)
                    print(matched)
                    return 0
            else:
                con.print(f"[bold #f43f5e]portal:[/] No matching directory found for '[white]{query_str}[/]'.")
                return 1

    # --------------------------------------------------------------------------
    # Subcommand Handlers
    # --------------------------------------------------------------------------

    def _handle_list(self, keywords: List[str], con: Console) -> int:
        """Displays ranked directories from zoxide database in a Rich Table."""
        assert self._zoxide_bin is not None
        cmd = [self._zoxide_bin, "query", "-l", "-s"]
        if keywords:
            cmd.extend(keywords)

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        except Exception as e:
            con.print(f"[bold #f43f5e]Failed to query zoxide:[/] {e}")
            return 1

        lines = [line.strip() for line in res.stdout.strip().splitlines() if line.strip()]
        if not lines:
            filter_msg = f" matching '{' '.join(keywords)}'" if keywords else ""
            con.print(f"[dim]No directory entries recorded in portal database{filter_msg}.[/]")
            return 0

        table = Table(title="[bold #00f0ff]🌀 Portal Database - Ranked Workspaces[/]", border_style="#0891b2")
        table.add_column("#", style="dim", justify="right", width=4)
        table.add_column("Score", style="bold #f59e0b", justify="right", width=8)
        table.add_column("Directory Path", style="#00f0ff", overflow="fold")
        table.add_column("State", justify="center", width=8)

        for idx, line in enumerate(lines, start=1):
            parts = line.split(maxsplit=1)
            if len(parts) == 2:
                score_str, path_str = parts[0], parts[1]
            else:
                score_str, path_str = "-", parts[0]

            path_obj = Path(path_str)
            exists = path_obj.exists() and path_obj.is_dir()
            state = "[bold #10b981]✔ active[/]" if exists else "[dim #f43f5e]✘ missing[/]"

            table.add_row(str(idx), score_str, path_str, state)

        con.print()
        con.print(table)
        con.print(f"[dim]Total: {len(lines)} directories tracked. Use 'z <keyword>' or 'portal <keyword>' to jump.[/]\n")
        return 0

    def _handle_add(self, paths: List[str], con: Console) -> int:
        """Adds specified or current directory to zoxide database."""
        assert self._zoxide_bin is not None
        target_paths = paths if paths else [str(Path.cwd())]

        for p in target_paths:
            target = Path(p).resolve()
            if not target.exists() or not target.is_dir():
                con.print(f"[bold #f43f5e]Error:[/] Directory '{target}' does not exist.")
                continue

            try:
                subprocess.run([self._zoxide_bin, "add", str(target)], check=True, stdout=subprocess.DEVNULL)
                con.print(f"[bold #10b981]✔ Added:[/] [white]{target}[/]")
            except Exception as e:
                con.print(f"[bold #f43f5e]Failed to add '{target}':[/] {e}")

        return 0

    def _handle_remove(self, paths: List[str], con: Console) -> int:
        """Removes a directory path from zoxide database."""
        assert self._zoxide_bin is not None
        if not paths:
            con.print("[bold #f43f5e]Error:[/] Please specify a directory path to remove.")
            con.print("[dim]Usage: kps portal rm <path>[/]")
            return 1

        for p in paths:
            try:
                subprocess.run([self._zoxide_bin, "remove", p], check=True, stdout=subprocess.DEVNULL)
                con.print(f"[bold #10b981]✔ Removed:[/] [white]{p}[/]")
            except Exception as e:
                con.print(f"[bold #f43f5e]Failed to remove '{p}':[/] {e}")

        return 0

    def _handle_query(self, keywords: List[str], con: Console) -> int:
        """Prints the best matching path for given keywords."""
        if not keywords:
            con.print("[bold #f43f5e]Error:[/] Keywords required for query.")
            return 1

        matched = self._query_zoxide_best(" ".join(keywords))
        if matched:
            print(matched)
            return 0
        else:
            con.print(f"[bold #f43f5e]portal:[/] No match found for '{' '.join(keywords)}'.")
            return 1

    def _handle_open(self, keywords: List[str], con: Console) -> int:
        """Resolves target directory and opens it in the native OS File Explorer."""
        if keywords:
            target_str = self._query_zoxide_best(" ".join(keywords))
            if not target_str:
                con.print(f"[bold #f43f5e]portal:[/] No match found for '{' '.join(keywords)}'.")
                return 1
            target = Path(target_str)
        else:
            target = Path.cwd()

        if not target.exists() or not target.is_dir():
            con.print(f"[bold #f43f5e]Error:[/] Target '{target}' is not a valid directory.")
            return 1

        con.print(f"[bold #10b981]✔ Opening in File Explorer:[/] [white]{target}[/]")
        try:
            if sys.platform == "win32":
                os.startfile(str(target))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(target)])
            else:
                subprocess.Popen(["xdg-open", str(target)])
            return 0
        except Exception as e:
            con.print(f"[bold #f43f5e]Failed to open explorer:[/] {e}")
            return 1

    def _handle_doctor(self, con: Console) -> int:
        """Diagnoses zoxide installation and environment state."""
        assert self._zoxide_bin is not None
        try:
            res = subprocess.run([self._zoxide_bin, "--version"], capture_output=True, text=True)
            ver = res.stdout.strip()
        except Exception:
            ver = "Unknown"

        data_dir = os.environ.get("_ZO_DATA_DIR")
        if not data_dir:
            if sys.platform == "win32":
                data_dir = os.path.expandvars(r"%LOCALAPPDATA%\zoxide")
            else:
                data_dir = os.path.expanduser("~/.local/share/zoxide")

        # Entry count
        entries = self._list_zoxide_entries("")
        fzf_available = shutil.which("fzf") is not None

        table = Table(title="[bold #00f0ff]🏥 Portal & zoxide Diagnostic[/]", border_style="#0891b2")
        table.add_column("Component", style="#00f0ff")
        table.add_column("Status / Value", style="white")

        table.add_row("zoxide binary", self._zoxide_bin)
        table.add_row("zoxide version", ver)
        table.add_row("Database path", data_dir)
        table.add_row("Tracked directories", f"{len(entries)} items")
        table.add_row("FZF fuzzy finder", "[bold #10b981]Available[/]" if fzf_available else "[dim]Not installed (Optional)[/]")
        table.add_row("Kapsel Hook Status", "[bold #10b981]Active (Auto-learning enabled)[/]")

        con.print()
        con.print(table)
        con.print()
        return 0

    def _handle_init_script(self, args: List[str], con: Console) -> int:
        """Generates shell integration snippet."""
        assert self._zoxide_bin is not None
        shell = args[0] if args else ("powershell" if sys.platform == "win32" else "bash")
        try:
            res = subprocess.run([self._zoxide_bin, "init", shell], capture_output=True, text=True)
            print(res.stdout)
            return 0
        except Exception as e:
            con.print(f"[bold #f43f5e]Failed to generate init script:[/] {e}")
            return 1

    # --------------------------------------------------------------------------
    # Helper & Query Methods
    # --------------------------------------------------------------------------

    def _async_add_directory(self, dir_path: str) -> None:
        """Non-blocking background invocation of 'zoxide add <path>'."""
        if not self._zoxide_bin:
            return

        def _worker() -> None:
            try:
                subprocess.run(
                    [self._zoxide_bin, "add", dir_path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=5,
                )
            except Exception:
                pass

        threading.Thread(target=_worker, daemon=True).start()

    def _query_zoxide_best(self, query: str) -> Optional[str]:
        """Queries zoxide for the best matching directory path."""
        if not self._zoxide_bin:
            return None

        try:
            tokens = query.split()
            cmd = [self._zoxide_bin, "query"] + tokens
            res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5)
            if res.returncode == 0 and res.stdout.strip():
                return res.stdout.strip()
        except Exception:
            pass

        return None

    def _list_zoxide_entries(self, filter_query: str = "") -> List[str]:
        """Lists directory entries recorded in zoxide database."""
        if not self._zoxide_bin:
            return []

        try:
            cmd = [self._zoxide_bin, "query", "-l"]
            if filter_query:
                cmd.extend(filter_query.split())
            res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5)
            if res.returncode == 0:
                return [line.strip() for line in res.stdout.strip().splitlines() if line.strip()]
        except Exception:
            pass

        return []

    def _run_zoxide_interactive(self, args: List[str]) -> int:
        """Runs an interactive zoxide subcommand inheriting stdout/stdin."""
        assert self._zoxide_bin is not None
        try:
            return subprocess.call([self._zoxide_bin] + args)
        except Exception as e:
            print(f"portal: execution error: {e}", file=sys.stderr)
            return 1

    def _render_help(self, con: Console) -> None:
        """Renders rich help panel for Portal."""
        help_text = (
            "[bold #00f0ff]Kapsel Portal - Smart Directory Teleportation (powered by zoxide)[/]\n"
            "[dim]Learns your project workspaces and enables instant navigation with minimal keystrokes.[/]\n\n"
            "[bold #a855f7]Quick Jumping (in Kapsel Terminal):[/]\n"
            "  [#10b981]z <keywords>[/]                Teleport to best matching workspace (e.g. 'z kap')\n"
            "  [#10b981]portal <keywords>[/]           Teleport to best matching workspace\n"
            "  [#10b981]z[/]                          Jump to home directory (~)\n"
            "  [#10b981]z -[/]                        Jump to previous directory\n\n"
            "[bold #a855f7]Management Commands (kps portal):[/]\n"
            "  [#00f0ff]kps portal ls [query][/]       List ranked directories and frecency scores\n"
            "  [#00f0ff]kps portal add [path][/]       Register directory in portal database (default: cwd)\n"
            "  [#00f0ff]kps portal rm <path>[/]        Remove directory path from portal database\n"
            "  [#00f0ff]kps portal query <keywords>[/] Resolve and print best matching path\n"
            "  [#00f0ff]kps portal open [query][/]     Jump and open directory in File Explorer\n"
            "  [#00f0ff]kps portal doctor[/]           Inspect zoxide installation, database, and health\n"
            "  [#00f0ff]kps portal edit[/]             Directly edit zoxide database\n"
            "  [#00f0ff]kps portal init [shell][/]     Generate external shell hook configuration\n\n"
            "[bold #a855f7]Examples:[/]\n"
            "  [dim]$[/] [white]z kap[/]                  [dim]# Teleports directly to ~/Desktop/Kapsel[/]\n"
            "  [dim]$[/] [white]kps portal ls[/]          [dim]# View all tracked workspaces and rankings[/]\n"
            "  [dim]$[/] [white]kps portal open[/]        [dim]# Opens current folder in Explorer / Finder[/]"
        )
        con.print(Panel(help_text, title="[bold #00f0ff]🌀 kps portal[/]", border_style="#0891b2"))


# Plugin class export for Kapsel Plugin Subsystem
Plugin = PortalPlugin
