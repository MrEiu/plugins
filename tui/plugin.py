"""
Kapsel TUI Plugin.
Registers and handles 'kps tui' command to launch the full-screen developer workbench.
All comments and docstrings are in English.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys
from typing import List, Optional

from rich.console import Console

from kapsel.core.plugin.base import KapselPlugin, PluginManifest
from kapsel.core.plugin.context import PluginContext
from .app import KapselWorkbenchApp


class TuiPlugin(KapselPlugin):
    """Full-screen developer workbench plugin for Kapsel."""

    @property
    def manifest(self) -> PluginManifest:
        return PluginManifest(
            id="tui",
            name="TUI",
            version="0.1.0",
            description="Full-screen developer workbench and split TUI for Kapsel featuring permanent file tree, native multi-tab PTY terminal, and Textual UI shell.",
            author="MrEiu",
            homepage="https://github.com/MrEiu/plugins",
        )

    def on_load(self, context: PluginContext) -> None:
        """Registers 'kps tui' command into Kapsel Command Registry."""
        context.register_kps_command(
            name="tui",
            handler=self.handle_tui_command,
            help_text="Launch full-screen developer workbench TUI (permanent file tree + native PTY terminal)",
            subcommands={
                "[path]": "Launch TUI in specified workspace folder (default: current directory)",
            },
            usage="kps tui [workspace_path]",
            scope="feature",
        )

    def on_unload(self) -> None:
        pass

    def handle_tui_command(self, args: List[str], console: Optional[Console] = None) -> int:
        """
        Launches the KapselWorkbenchApp full-screen TUI.
        """
        target_path = Path.cwd()
        if args and not args[0].startswith("-"):
            candidate = Path(args[0]).resolve()
            if candidate.exists() and candidate.is_dir():
                target_path = candidate

        try:
            app = KapselWorkbenchApp(workspace_path=target_path)
            app.run()
            return 0
        except Exception as e:
            con = console or Console(legacy_windows=False)
            con.print(f"[bold #f43f5e]Error launching TUI:[/] {e}")
            return 1


Plugin = TuiPlugin
