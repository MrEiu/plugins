"""
Template Plugin for Kapsel.
Canonical reference implementation illustrating:
1. PluginManifest declaration and metadata standards.
2. Lifecycle hooks: on_load and on_unload.
3. Pre-execution command filter (HookType.FILTER_COMMAND).
4. Dynamic tab completion provider (HookType.PROVIDE_COMPLETIONS).
5. Functional command registration under 'kps' namespace.
6. Error boundary and user feedback patterns.

All comments and docstrings are in English.
"""

from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple

from rich.console import Console

from kapsel.core.plugin.base import KapselPlugin, PluginManifest
from kapsel.core.plugin.context import PluginContext
from kapsel.core.plugin.hooks import HookType

# Safe import pattern: try relative import first (for standalone package portability),
# then fallback to absolute workspace import.
try:
    from .engine import render_info_card, resolve_tool_executable
    from .install import is_tool_installed, print_installation_guide
except ImportError:
    from plugins.template.engine import render_info_card, resolve_tool_executable
    from plugins.template.install import is_tool_installed, print_installation_guide


class TemplatePlugin(KapselPlugin):
    """
    TemplatePlugin serves as the gold-standard reference boilerplate for Kapsel plugins.
    Copy this directory to create your own custom plugins!
    """

    manifest = PluginManifest(
        id="template",
        name="Template",
        version="0.1.0",
        description="Canonical boilerplate and development reference for Kapsel plugins.",
        author="Kapsel Team",
        homepage="https://github.com/MrEiu/plugins/tree/master/template",
        min_kapsel_version="0.1.0",
        tags=["template", "boilerplate", "guide", "development", "example"],
    )

    def __init__(self) -> None:
        super().__init__()
        self.context: Optional[PluginContext] = None

    def on_load(self, context: PluginContext) -> None:
        """
        Called when the plugin is dynamically loaded by Kapsel PluginManager.
        Register hooks, commands, and autocompletion providers here.
        """
        self.context = context

        # 1. Register Pre-execution Command Filter
        # Allows intercepting CLI inputs before they reach the host shell (pwsh/bash).
        context.register_hook(HookType.FILTER_COMMAND, self.filter_command)

        # 2. Register Dynamic Autocompletion Provider
        # Feeds candidates to Kapsel's floating dropdown menu when typing in the prompt.
        context.register_hook(HookType.PROVIDE_COMPLETIONS, self.provide_completions)

        # 3. Register Functional Command under 'kps' namespace
        # Per Kapsel guidelines, plugin commands MUST live under 'kps' (e.g. 'kps template').
        context.register_kps_command(
            name="template",
            handler=self.handle_template,
            help_text="Reference template command demonstrating plugin features",
            usage="kps template [subcommand|options]",
            scope="feature",
        )

    def on_unload(self) -> None:
        """
        Called when the plugin is unloaded or during terminal shutdown.
        Clean up background threads, temp files, or open handles here.
        """
        self.context = None

    # --------------------------------------------------------------------------
    # Command Handlers
    # --------------------------------------------------------------------------

    def handle_template(self, args: List[str], console: Optional[Console] = None) -> int:
        """
        Main execution handler for 'kps template [args]'.
        Must return an integer exit code (0 for success, non-zero for error).
        """
        con = console or Console()

        if not args or args[0] in ("-h", "--help", "help"):
            self._render_help(con)
            return 0

        subcommand = args[0].lower()

        if subcommand == "info":
            # Example: Rendering a structured Rich status card
            info_data = {
                "Plugin ID": self.manifest.id,
                "Version": self.manifest.version,
                "Author": self.manifest.author,
                "Homepage": self.manifest.homepage,
                "Status": "Active & Loaded",
            }
            render_info_card("Template Plugin Metadata", info_data, con, status_success=True)
            return 0

        if subcommand == "check":
            # Example: Dependency detection
            if is_tool_installed():
                con.print("[bold #10b981]✔ Dependency check passed: external tool is ready.[/]")
                return 0
            print_installation_guide(con)
            return 1

        con.print(f"[bold #f43f5e]Unknown subcommand:[/] '{subcommand}'. Run 'kps template help' for usage.")
        return 1

    # --------------------------------------------------------------------------
    # Hooks: Command Filtering & Rewriting
    # --------------------------------------------------------------------------

    def filter_command(self, raw_command: str) -> Tuple[bool, str]:
        """
        Inspects or transforms commands entered by the user.
        Return:
          - (False, raw_command): Ignore command, pass through to shell or other plugins.
          - (True, ""): Fully handled in-process by plugin; do not execute in host shell.
          - (True, rewritten_cmd): Rewrite command before sending to executor (e.g. 'foo | bar').
        """
        stripped = raw_command.strip()
        if not stripped:
            return False, raw_command

        tokens = stripped.split()
        prefix = tokens[0].lower()

        # Example: Intercepting a standalone shortcut command, e.g. 'tmpl <arg>'
        if prefix == "tmpl":
            con = Console()
            args = tokens[1:]
            self.handle_template(args, con)
            # Handled directly in-process; prevent host shell from attempting to run 'tmpl'
            return True, ""

        return False, raw_command

    # --------------------------------------------------------------------------
    # Hooks: Autocompletions
    # --------------------------------------------------------------------------

    def provide_completions(self, text_before_cursor: str) -> List[Dict[str, Any]]:
        """
        Provides autocomplete items when the cursor is in the prompt line.
        Each item dictionary should contain:
          - text: The replacement or completion string.
          - display: Text shown in the candidate menu.
          - display_meta: Dim hint text shown on the right.
          - start_position: Relative negative offset for buffer replacement.
        """
        stripped = text_before_cursor.lstrip()

        # Trigger completions for 'kps template ' or shortcut 'tmpl '
        matched_prefix = None
        for p in ("kps template ", "tmpl "):
            if stripped.startswith(p):
                matched_prefix = p
                break

        if not matched_prefix:
            return []

        remainder = stripped[len(matched_prefix):]

        subcommands = [
            {"text": "info", "display": "info", "display_meta": "Display plugin metadata"},
            {"text": "check", "display": "check", "display_meta": "Verify external dependencies"},
            {"text": "help", "display": "help", "display_meta": "Show command help"},
        ]

        # Filter by what the user has typed so far
        candidates = []
        for sub in subcommands:
            if sub["text"].startswith(remainder.lower()):
                candidates.append({
                    "text": sub["text"],
                    "display": sub["display"],
                    "display_meta": sub["display_meta"],
                    "start_position": -len(remainder),
                })
        return candidates

    # --------------------------------------------------------------------------
    # Help Presentation
    # --------------------------------------------------------------------------

    def _render_help(self, con: Console) -> None:
        """Prints formatted help information for the plugin."""
        con.print("\n[bold #00f0ff]Kapsel Plugin Template - Reference Implementation[/]")
        con.print("[dim]Use this plugin as a starting point to author custom Kapsel plugins.[/]\n")
        con.print("[bold white]Usage:[/]")
        con.print("  [#38bdf8]kps template info[/]     Show plugin metadata and status card")
        con.print("  [#38bdf8]kps template check[/]    Verify third-party CLI dependencies")
        con.print("  [#38bdf8]kps template help[/]     Display this help manual")
        con.print("  [#38bdf8]tmpl [args][/]           Shortcut alias handled via filter_command\n")


# Standard module export: Kapsel PluginManager expects 'Plugin' attribute
Plugin = TemplatePlugin
