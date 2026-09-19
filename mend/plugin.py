"""
Kapsel Mend Plugin.
Provides concurrent plugin dependency checking, automated dependency repair,
and interactive configuration/cache cleanup.

All comments and descriptions are in English.
"""

from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.panel import Panel

from kapsel.core.plugin.base import KapselPlugin, PluginManifest
from kapsel.core.plugin.context import PluginContext
from kapsel.ui.banner import ensure_utf8_io

try:
    from .checker import (
        concurrent_check_all_dependencies,
        auto_fix_missing_dependencies,
        ToolCheckResult,
    )
    from .cleaner import (
        scan_cleanable_targets,
        interactive_select_cleanable_categories,
        execute_clean,
    )
except ImportError:
    from plugins.mend.checker import (
        concurrent_check_all_dependencies,
        auto_fix_missing_dependencies,
        ToolCheckResult,
    )
    from plugins.mend.cleaner import (
        scan_cleanable_targets,
        interactive_select_cleanable_categories,
        execute_clean,
    )


class MendPlugin(KapselPlugin):
    """
    Kapsel 'mend' plugin: Diagnostic self-healing health checker and
    interactive configuration cleaner.
    """

    manifest = PluginManifest(
        id="mend",
        name="Mend",
        version="0.1.0",
        description="Self-healing diagnostic health checker and interactive configuration cleaner for Kapsel.",
        author="Kapsel Team",
        homepage="https://github.com/MrEiu/plugins/tree/master/mend",
        min_kapsel_version="0.1.0",
        tags=["diagnostics", "doctor", "health", "cleaner", "maintenance", "repair"],
    )

    def __init__(self) -> None:
        super().__init__()
        self.context: Optional[PluginContext] = None

    def on_load(self, context: PluginContext) -> None:
        """Registers the 'mend' command under the 'kps' namespace."""
        self.context = context

        context.register_kps_command(
            name="mend",
            handler=self.handle_mend,
            help_text="Inspect plugin dependencies, auto-fix missing tools, and clean configurations",
            usage="kps mend [check | fix | clean | all] [options]",
            subcommands={
                "check": "Concurrently check all plugin dependencies and report missing tools",
                "fix": "Auto-install all missing plugin tool dependencies",
                "clean": "Interactively select and clean temporary files, logs, and stale configs",
                "all": "Run both dependency inspection and interactive configuration cleaner",
            },
            scope="feature",
        )

    def handle_mend(self, args: List[str], console: Optional[Console] = None) -> int:
        """Handles 'kps mend' invocations."""
        ensure_utf8_io()
        con = console or Console(legacy_windows=False)

        subcmd = args[0].lower() if args else "check"

        if subcmd in ("-h", "--help", "help"):
            self._show_help(con)
            return 0

        if subcmd in ("check", "doctor", "status"):
            _, missing = concurrent_check_all_dependencies(con)
            if missing and any(a in ("--fix", "-f") for a in args):
                return auto_fix_missing_dependencies(missing, con)
            return 0

        if subcmd in ("fix", "repair", "install"):
            _, missing = concurrent_check_all_dependencies(con)
            return auto_fix_missing_dependencies(missing, con)

        if subcmd in ("clean", "cleanup", "purge", "gc"):
            categories = scan_cleanable_targets()
            selected = interactive_select_cleanable_categories(categories, con)
            if selected:
                return execute_clean(selected, con)
            return 0

        if subcmd == "all":
            con.print("[bold #00f0ff]=== Step 1: Plugin Dependency Health Check ===[/]")
            _, missing = concurrent_check_all_dependencies(con)
            if missing and any(a in ("--fix", "-f") for a in args):
                auto_fix_missing_dependencies(missing, con)

            con.print("\n[bold #00f0ff]=== Step 2: Configuration & Storage Cleanup ===[/]")
            categories = scan_cleanable_targets()
            selected = interactive_select_cleanable_categories(categories, con)
            if selected:
                execute_clean(selected, con)
            return 0

        con.print(f"[bold #f43f5e]Unknown subcommand:[/] '{subcmd}'")
        con.print("[dim]Available subcommands: check, fix, clean, all[/]\n")
        return 1

    def _show_help(self, con: Console) -> None:
        """Renders help panel for kps mend."""
        con.print(
            Panel(
                "[bold white]Kapsel Mend: Health Diagnostics & Storage Cleaner[/]\n"
                "[dim]Self-healing tool to verify plugin dependencies and maintain clean storage.[/]\n\n"
                "[bold #00f0ff]Usage:[/]\n"
                "  kps mend [subcommand] [options]\n\n"
                "[bold #00f0ff]Subcommands:[/]\n"
                "  [cyan]check[/]  Concurrently verify all plugin dependencies and report missing tools\n"
                "  [cyan]fix[/]    Auto-install all missing external dependencies via declarative tools.yaml\n"
                "  [cyan]clean[/]  Interactively select and clean session logs, backup configs, and caches\n"
                "  [cyan]all[/]    Run dependency inspection followed by interactive storage cleaner\n\n"
                "[bold #00f0ff]Examples:[/]\n"
                "  kps mend                 (runs health check)\n"
                "  kps mend check --fix     (checks and auto-fixes any missing dependencies)\n"
                "  kps mend clean           (opens interactive configuration & cache cleaner)",
                title="[bold #a855f7]kps mend[/]",
                border_style="#00f0ff",
            )
        )


Plugin = MendPlugin
