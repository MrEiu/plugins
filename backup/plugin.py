"""
Backup Plugin for Kapsel.
Lightweight zero-pollution file & folder version backup and interactive restoration CLI powered by GitKeep.
All comments and docstrings are in English.
"""

from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple

from rich.console import Console
from rich.panel import Panel

from kapsel.core.plugin.base import KapselPlugin, PluginManifest
from kapsel.core.plugin.context import PluginContext
from kapsel.core.plugin.hooks import HookType

try:
    from .engine import (
        resolve_bk_command,
        get_backup_history,
        select_backup_version_interactive,
        run_bk_passthrough,
    )
    from .install import auto_install, print_installation_guide
except ImportError:
    from plugins.backup.engine import (
        resolve_bk_command,
        get_backup_history,
        select_backup_version_interactive,
        run_bk_passthrough,
    )
    from plugins.backup.install import auto_install, print_installation_guide


class BackupPlugin(KapselPlugin):
    """
    Kapsel Backup Plugin: Zero-pollution, zero-setup file and folder backup
    and interactive snapshot restoration engine powered by GitKeep.
    """

    manifest = PluginManifest(
        id="backup",
        name="Backup",
        version="0.1.1",
        description="Lightweight zero-pollution file & folder version backup and interactive restoration CLI powered by GitKeep.",
        author="Kapsel Team",
        homepage="https://github.com/MrEiu/plugins/tree/master/backup",
        min_kapsel_version="0.1.0",
        tags=["backup", "restore", "git", "undo", "snapshot", "vcs", "gitkeep", "npm"],
    )

    def __init__(self) -> None:
        super().__init__()
        self.context: Optional[PluginContext] = None

    def on_load(self, context: PluginContext) -> None:
        self.context = context

        # 1. Pre-execution filter: intercepts 'bk', 'backup', 'kps bk', 'kps backup'
        context.register_hook(HookType.FILTER_COMMAND, self.filter_command)

        # 2. Dynamic autocompletions
        context.register_hook(HookType.PROVIDE_COMPLETIONS, self.provide_completions)

        # 3. Register functional command under kps namespace
        context.register_kps_command(
            name="backup",
            handler=self.handle_backup,
            help_text="Lightweight zero-pollution backup and restore manager powered by GitKeep",
            usage="kps backup [command] [args...] / bk [args...]",
            subcommands={
                "backup": "Save backup of current directory or file (default: .)",
                "log": "View backup history with relative time",
                "diff": "Show changes since the latest backup",
                "undo": "Instantly roll back to previous backup version",
                "restore": "Interactively restore directory or file from snapshot",
                "show": "Inspect commit diffstat or file content",
                "status": "Show project backup binding status and 8-character ID",
                "list": "List all registered backup projects on this machine",
                "init": "Manually initialize external Git backup repository",
                "install": "Install or update gitkeep-cli globally via npm/pnpm/bun/yarn",
            },
            scope="feature",
        )

        # Also register 'bk' alias under kps namespace if supported
        context.register_kps_command(
            name="bk",
            handler=self.handle_backup,
            help_text="Alias for kps backup",
            usage="kps bk [command] [args...]",
            scope="feature",
        )

    def filter_command(self, raw_command: str) -> Tuple[bool, str]:
        """
        Intercepts:
        1. 'bk [args...]'
        2. 'backup [args...]'
        3. 'kps bk [args...]'
        4. 'kps backup [args...]'
        """
        stripped = raw_command.strip()
        if not stripped:
            return False, raw_command

        tokens = stripped.split()
        prefix = tokens[0].lower()

        if prefix in ("bk", "backup"):
            con = Console(legacy_windows=False)
            self.handle_backup(tokens[1:], con)
            return True, ""

        if prefix == "kps" and len(tokens) >= 2:
            sub = tokens[1].lower()
            if sub in ("bk", "backup"):
                con = Console(legacy_windows=False)
                self.handle_backup(tokens[2:], con)
                return True, ""

        return False, raw_command

    def provide_completions(self, context: Any) -> List[Any]:
        """
        Provides rich autocompletions for 'bk', 'backup', and 'kps backup'.
        """
        text = getattr(context, "text_before_cursor", "")
        stripped = text.strip()
        tokens = stripped.split()

        if not tokens:
            return []

        first = tokens[0].lower()
        is_kps_bk = (first == "kps" and len(tokens) >= 2 and tokens[1].lower() in ("bk", "backup"))
        is_direct = first in ("bk", "backup")

        if not (is_kps_bk or is_direct):
            return []

        # Current word being completed
        current_word = tokens[-1] if not text.endswith(" ") else ""

        commands = [
            ("backup", "Backup directory or file immediately"),
            ("log", "View commit history with relative time"),
            ("diff", "Show changes since the latest backup"),
            ("undo", "Roll back working tree to previous backup"),
            ("restore", "Restore snapshot (interactive selector if omitted)"),
            ("show", "Inspect snapshot diffstat or file content"),
            ("status", "Show project backup binding status"),
            ("list", "List all registered backup projects"),
            ("init", "Initialize external Git backup repository"),
            ("install", "Install gitkeep-cli globally via npm/pnpm/bun/yarn"),
            ("-m", "Custom commit message"),
            ("-n", "Limit number of history items"),
            ("--json", "Output result in JSON format"),
            ("--project", "Target project root directory"),
            ("-h", "Show help message"),
            ("-v", "Show GitKeep version"),
        ]

        from prompt_toolkit.completion import Completion

        results = []
        for cmd, desc in commands:
            if not current_word or cmd.startswith(current_word.lower()):
                results.append(
                    Completion(
                        text=cmd,
                        start_position=-len(current_word),
                        display=cmd,
                        display_meta=desc,
                    )
                )

        return results

    def handle_backup(self, args: List[str], con: Optional[Console] = None) -> int:
        """
        Main backup and restore handler.
        Supports interactive snapshot selection when 'restore' is called without version hash.
        """
        console = con or Console(legacy_windows=False)

        # Handle explicit 'bk install'
        if args and args[0].lower() in ("install", "setup", "update-cli"):
            return 0 if auto_install(console) else 1

        # Check for interactive restore:
        # e.g. 'bk restore' or 'bk restore .'
        if args and args[0].lower() in ("restore", "checkout"):
            # Check if a version argument is provided
            # Pattern: ['restore'] or ['restore', '.']
            needs_interactive = False
            target_path = "."
            if len(args) == 1:
                needs_interactive = True
            elif len(args) == 2 and args[1] in (".", "./", ".\\"):
                needs_interactive = True

            if needs_interactive:
                commits, err = get_backup_history(limit=40)
                if err:
                    console.print(f"[bold red]Failed to load backup history:[/bold red] {err}")
                    return 1

                if not commits:
                    console.print("[yellow]No backup snapshots found for this directory.[/yellow]")
                    console.print("[dim]Run 'bk' to create your first backup snapshot.[/dim]")
                    return 0

                selected_version = select_backup_version_interactive(commits)
                if not selected_version:
                    console.print("[dim]Snapshot restoration cancelled.[/dim]")
                    return 0

                console.print(f"\n[bold cyan]Restoring snapshot [yellow]{selected_version}[/yellow]...[/bold cyan]")
                return run_bk_passthrough(["restore", selected_version], con=console)

        # Passthrough standard execution
        return run_bk_passthrough(args, con=console)


# Standard plugin alias
Plugin = BackupPlugin
