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
        version="0.1.4",
        description="Smart directory teleportation and directory-bound initialization hook (.portal) powered by zoxide.",
        author="Kapsel Team",
        homepage="https://github.com/MrEiu/plugins/tree/master/portal",
        min_kapsel_version="0.1.0",
        tags=["zoxide", "cd", "navigation", "portal", "hook", "frecency", "workspace"],
    )

    def __init__(self) -> None:
        super().__init__()
        self.context: Optional[PluginContext] = None
        self._zoxide_bin: Optional[str] = None
        self._last_recorded_cwd: Optional[str] = None
        self._cached_recent_dirs: List[str] = []
        self._cache_lock = threading.Lock()
        self._is_running_hook: bool = False

    def on_load(self, context: PluginContext) -> None:
        self.context = context
        self._zoxide_bin = _resolve_zoxide_executable()

        # 1. Pre-execution filter: intercepts 'z <query>' and 'portal <query>'
        context.register_hook(HookType.FILTER_COMMAND, self.filter_command)

        # 2. Command execution tracking: auto-learns visited directories and triggers hooks
        context.register_hook(HookType.ON_AFTER_EXECUTE, self.on_after_execute)

        # 3. Dynamic autocompletion for portal and zoxide paths
        context.register_hook(HookType.PROVIDE_COMPLETIONS, self.provide_completions)

        # 4. Register functional management command: 'kps portal'
        context.register_kps_command(
            name="portal",
            handler=self.handle_portal,
            help_text="Smart directory teleportation and workspace auto-init hooks powered by zoxide",
            subcommands={
                "ls": "List ranked directories in portal database",
                "add": "Register a directory in portal database",
                "rm": "Remove a directory from portal database",
                "query": "Resolve and print matching directory path",
                "open": "Open directory in File Explorer / Finder",
                "doctor": "Inspect zoxide status and health",
                "init": "Generate shell integration script",
                "hook": "Manage directory-bound initialization hooks (.portal)",
            },
            usage="kps portal [ls|add|rm|query|open|doctor|init|hook] [args...]",
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
        Executes .portal directory initialization hook if present in new working directory.
        """
        if exit_code != 0 or self._is_running_hook:
            return

        try:
            current_cwd = str(Path.cwd().resolve())
            if current_cwd != self._last_recorded_cwd:
                self._last_recorded_cwd = current_cwd
                self._async_add_directory(current_cwd)
                self._execute_portal_hook(Path(current_cwd))
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

        remainder = stripped[len(matched_prefix):]

        # Autocomplete for hook subcommand: 'kps portal hook <Tab>'
        if remainder.startswith("hook "):
            hook_prefix = remainder[5:].strip().lower()
            hook_actions = [
                ("status", "Show .portal hook status in current directory"),
                ("init", "Create a .portal template file in current directory"),
                ("add", "Append command(s) directly into .portal"),
                ("paste", "Paste and write multiple commands into .portal"),
                ("edit", "Open .portal in nano/terminal editor"),
                ("run", "Execute .portal commands immediately"),
                ("rm", "Delete .portal file from current directory"),
            ]
            return [
                {
                    "text": act,
                    "display": act,
                    "display_meta": f"🌀 {desc}",
                    "start_position": -len(hook_prefix) if hook_prefix else 0,
                }
                for act, desc in hook_actions
                if act.startswith(hook_prefix)
            ]

        # Autocomplete for portal subcommands: 'kps portal <Tab>'
        if matched_prefix.startswith("kps") or matched_prefix.startswith("kapsel"):
            tokens = remainder.split()
            if len(tokens) == 0 or (len(tokens) == 1 and not remainder.endswith(" ")):
                sub_prefix = tokens[0].lower() if tokens else ""
                sub_cmds = [
                    ("ls", "List ranked directories"),
                    ("add", "Register directory in database"),
                    ("rm", "Remove directory from database"),
                    ("query", "Print matching directory path"),
                    ("open", "Open directory in File Explorer"),
                    ("doctor", "Inspect zoxide health"),
                    ("init", "Generate shell integration script"),
                    ("hook", "Manage directory initialization hook (.portal)"),
                ]
                return [
                    {
                        "text": sc,
                        "display": sc,
                        "display_meta": f"🌀 {desc}",
                        "start_position": -len(sub_prefix) if sub_prefix else 0,
                    }
                    for sc, desc in sub_cmds
                    if sc.startswith(sub_prefix)
                ]

        if not self._zoxide_bin:
            return []

        if remainder.endswith(" ") or not remainder:
            start_pos = 0
            query = ""
        else:
            curr_token = remainder.split()[-1]
            start_pos = -len(curr_token)
            query = remainder.strip()

        entries = self._list_zoxide_entries(query)

        candidates = []
        for path_str in entries[:15]:
            path_obj = Path(path_str)
            basename = path_obj.name or path_str
            candidates.append({
                "text": basename,
                "display": f"{basename}  [dim]({path_str})[/]",
                "display_meta": "[portal]",
                "start_position": start_pos,
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
        elif subcmd in ("hook", "bind", "autorun"):
            return self._handle_hook(args[1:], con)
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

    def _handle_hook(self, args: List[str], con: Console) -> int:
        """
        Manages the .portal directory-bound initialization hook in the current directory.
        Subcommands:
          kps portal hook              -> view status / cat
          kps portal hook init         -> create template .portal
          kps portal hook edit         -> open in editor
          kps portal hook run          -> run commands immediately
          kps portal hook rm           -> delete .portal
        """
        action = args[0].lower() if args else "status"
        cwd = Path.cwd()
        hook_path = cwd / ".portal"

        if action in ("status", "cat", "show"):
            if not hook_path.exists():
                con.print(f"[dim]No .portal hook found in current directory:[/] [bold]{cwd}[/]")
                con.print("[dim]Create one using:[/] [bold #00f0ff]kps portal hook init[/]\n")
                return 0

            content = hook_path.read_text(encoding="utf-8", errors="replace")
            con.print(f"\n[bold #00f0ff]🌀 Portal Hook (.portal) in[/] [bold #a855f7]{cwd}[/]:")
            lines = [ln.strip() for ln in content.splitlines() if ln.strip() and not ln.strip().startswith("#")]
            con.print(Panel(content.strip(), border_style="#0891b2", title=f"{len(lines)} active command(s)"))
            con.print("[dim]Edit with 'kps portal hook edit' · Test run with 'kps portal hook run'[/]\n")
            return 0

        elif action in ("init", "create", "new"):
            if hook_path.exists():
                con.print(f"[yellow]A .portal hook already exists in:[/] [bold]{hook_path}[/]")
                con.print("[dim]To edit it, run:[/] [bold #00f0ff]kps portal hook edit[/]\n")
                return 0

            template = (
                "# .portal - Directory Auto-Run Hook\n"
                "# Commands in this file are executed sequentially whenever you enter this directory.\n"
                "# Lines starting with '#' are ignored.\n\n"
                "# Example commands:\n"
                "# git status -s\n"
            )
            hook_path.write_text(template, encoding="utf-8")
            con.print(f"[bold #10b981]✔ Created .portal hook file at:[/] [bold #00f0ff]{hook_path}[/]")
            con.print("[dim]Run 'kps portal hook edit' to customize initialization commands.[/]\n")
            return 0

        elif action in ("add", "append", "+"):
            if len(args) < 2:
                con.print("[yellow]Usage:[/] [bold #00f0ff]kps portal hook add <command>[/]")
                con.print("[dim]Example: kps portal hook add git status -s[/]\n")
                return 1

            new_cmd = " ".join(args[1:]).strip()
            if not hook_path.exists():
                template = (
                    "# .portal - Directory Auto-Run Hook\n"
                    "# Commands in this file are executed sequentially whenever you enter this directory.\n"
                    "# Lines starting with '#' are ignored.\n\n"
                )
                hook_path.write_text(template + new_cmd + "\n", encoding="utf-8")
            else:
                existing = hook_path.read_text(encoding="utf-8", errors="replace")
                if existing and not existing.endswith("\n"):
                    existing += "\n"
                hook_path.write_text(existing + new_cmd + "\n", encoding="utf-8")

            con.print(f"[bold #10b981]✔ Added command to .portal:[/] [white]{new_cmd}[/]\n")
            return 0

        elif action in ("paste", "set", "write"):
            con.print("\n[bold #00f0ff]📋 Paste / Type commands for .portal[/] [dim](Press Enter on empty line or Ctrl+Z/Ctrl+D to save):[/]")
            input_lines: List[str] = []
            try:
                while True:
                    line = input("  ❯ ")
                    if not line.strip() and input_lines:
                        break
                    if line.strip():
                        input_lines.append(line.strip())
            except (EOFError, KeyboardInterrupt):
                pass

            if not input_lines:
                con.print("[dim]No commands entered. Operation cancelled.[/]\n")
                return 0

            header = (
                "# .portal - Directory Auto-Run Hook\n"
                "# Commands in this file are executed sequentially whenever you enter this directory.\n\n"
            )
            hook_path.write_text(header + "\n".join(input_lines) + "\n", encoding="utf-8")
            con.print(f"[bold #10b981]✔ Saved {len(input_lines)} command(s) to:[/] [bold #00f0ff]{hook_path}[/]\n")
            return 0

        elif action in ("edit", "open"):
            if not hook_path.exists():
                self._handle_hook(["init"], con)

            return self._open_editor(hook_path, con)

        elif action in ("run", "exec"):
            if not hook_path.exists():
                con.print(f"[bold #f43f5e]Error:[/] No .portal file found in [white]{cwd}[/]")
                return 1
            executed = self._execute_portal_hook(cwd, con)
            return 0 if executed else 1

        elif action in ("rm", "remove", "del", "delete"):
            if not hook_path.exists():
                con.print(f"[dim]No .portal hook to remove in {cwd}[/]\n")
                return 0
            try:
                hook_path.unlink()
                con.print(f"[bold #10b981]✔ Removed .portal hook from:[/] [white]{cwd}[/]\n")
                return 0
            except Exception as e:
                con.print(f"[bold #f43f5e]Failed to delete .portal:[/] {e}")
                return 1

        else:
            con.print(f"[bold #f43f5e]Unknown hook action:[/] '{action}' (options: status, init, add, paste, edit, run, rm)")
            return 1

    def _open_editor(self, file_path: Path, con: Console) -> int:
        """
        Opens file in the best available editor with nano priority:
        1. $EDITOR / $VISUAL environment variable
        2. Terminal editors: nano -> micro -> vim -> vi
        3. Platform native fallbacks: notepad on Windows, xdg-open on Linux, open on macOS
        """
        # 1. Custom environment variable
        custom_editor = os.environ.get("EDITOR") or os.environ.get("VISUAL")
        if custom_editor:
            exe = shutil.which(custom_editor)
            if exe:
                con.print(f"[dim]Opening in $EDITOR ({custom_editor}):[/] [bold #00f0ff]{file_path}[/]")
                try:
                    return subprocess.call([exe, str(file_path)])
                except Exception:
                    pass

        # 2. Terminal-based editors (nano prioritized)
        for tui_name in ("nano", "micro", "vim", "vi"):
            exe = shutil.which(tui_name)
            if exe:
                con.print(f"[dim]Opening in {tui_name}:[/] [bold #00f0ff]{file_path}[/]")
                try:
                    return subprocess.call([exe, str(file_path)])
                except Exception:
                    pass

        # 3. System desktop fallbacks
        con.print(f"[dim]Opening in system default editor:[/] [bold #00f0ff]{file_path}[/]")
        try:
            if sys.platform == "win32":
                notepad = shutil.which("notepad.exe") or "notepad.exe"
                return subprocess.call([notepad, str(file_path)])
            elif sys.platform == "darwin":
                return subprocess.call(["open", str(file_path)])
            else:
                return subprocess.call(["xdg-open", str(file_path)])
        except Exception as e:
            con.print(f"[bold #f43f5e]Failed to open editor: {e}[/]")
            con.print("[dim]Tip: You can use 'kps portal hook add <cmd>' or 'kps portal hook paste' directly.[/]\n")
            return 1

    def _execute_portal_hook(self, dir_path: Path, console: Optional[Console] = None) -> bool:
        """
        Reads and executes sequentially all non-comment commands in a '.portal' file.
        """
        hook_file = dir_path / ".portal"
        if not hook_file.exists() or not hook_file.is_file():
            return False

        try:
            raw_text = hook_file.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return False

        commands: List[str] = []
        for line in raw_text.splitlines():
            cleaned = line.strip()
            if cleaned and not cleaned.startswith("#"):
                commands.append(cleaned)

        if not commands:
            return False

        con = console or Console(legacy_windows=False)
        con.print(f"\n[bold #00f0ff]🌀 Portal Hook:[/] Executing directory initialization in [dim]{dir_path.name}[/] ({len(commands)} command{'s' if len(commands) > 1 else ''})...")

        self._is_running_hook = True
        try:
            shell_name = "cmd" if sys.platform == "win32" else "sh"
            shell_bin = None
            if self.context and hasattr(self.context, "environment"):
                try:
                    s_name, s_path = self.context.environment.detect_shell()
                    shell_name = s_name
                    shell_bin = s_path
                except Exception:
                    pass

            for idx, cmd in enumerate(commands, 1):
                con.print(f"  [dim]{idx}/{len(commands)}[/] [bold #a855f7]❯[/] [white]{cmd}[/]")
                try:
                    if sys.platform == "win32":
                        if shell_name in ("pwsh", "powershell") and (shell_bin or shutil.which(shell_name)):
                            exe = shell_bin or shutil.which(shell_name)
                            res = subprocess.run([exe, "-Command", cmd], cwd=str(dir_path))
                        else:
                            res = subprocess.run(cmd, shell=True, cwd=str(dir_path))
                    else:
                        shell_exe = shell_bin or shutil.which("bash") or "/bin/sh"
                        res = subprocess.run([shell_exe, "-c", cmd], cwd=str(dir_path))

                    if res.returncode != 0:
                        con.print(f"  [bold #f43f5e]✘ Command exited with code {res.returncode}[/]")
                except Exception as err:
                    con.print(f"  [bold #f43f5e]✘ Execution error:[/] {err}")

            con.print("[bold #10b981]✔ Portal initialization complete.[/]\n")
            return True
        finally:
            self._is_running_hook = False

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
            "[bold #00f0ff]Kapsel Portal - Smart Directory Teleportation & Auto-Init (powered by zoxide)[/]\n"
            "[dim]Learns your workspaces and runs directory-bound .portal initialization hooks.[/]\n\n"
            "[bold #a855f7]Quick Jumping (in Kapsel Terminal):[/]\n"
            "  [#10b981]z <keywords>[/]                Teleport to best matching workspace (e.g. 'z kap')\n"
            "  [#10b981]portal <keywords>[/]           Teleport to best matching workspace\n"
            "  [#10b981]z[/]                          Jump to home directory (~)\n"
            "  [#10b981]z -[/]                        Jump to previous directory\n\n"
            "[bold #a855f7]Management Commands (kps portal):[/]\n"
            "  [#00f0ff]kps portal hook [subcmd][/]    Manage directory auto-run hook (.portal)\n"
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
            "  [dim]$[/] [white]kps portal hook init[/]   [dim]# Creates .portal hook file in current directory[/]\n"
            "  [dim]$[/] [white]kps portal hook edit[/]   [dim]# Edits .portal commands in text editor[/]\n"
            "  [dim]$[/] [white]kps portal ls[/]          [dim]# View all tracked workspaces and rankings[/]"
        )
        con.print(Panel(help_text, title="[bold #00f0ff]🌀 kps portal[/]", border_style="#0891b2"))


# Plugin class export for Kapsel Plugin Subsystem
Plugin = PortalPlugin
