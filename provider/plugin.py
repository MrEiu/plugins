"""
Provider Plugin for Kapsel.
Bridges cc-switch (SaladDay/cc-switch-cli) to provide seamless switching
and management for AI coding assistant providers, models, and proxy endpoints.
Supports both interactive TUI mode and CLI subcommands.
All comments and descriptions are in English.
"""

import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import List, Optional

from rich.console import Console

from kapsel.core.plugin.base import KapselPlugin, PluginManifest
from kapsel.core.plugin.context import PluginContext
from kapsel.storage.config import get_kapsel_dir
from kapsel.ui.banner import ensure_utf8_io

ensure_utf8_io()


def resolve_cc_switch_executable() -> Optional[str]:
    """
    Locates the cc-switch binary across system PATH, ~/.kapsel/bin,
    Homebrew, Cargo, npm, and standard Unix bin paths.
    """
    p = shutil.which("cc-switch")
    if p:
        return p

    kapsel_bin = get_kapsel_dir() / "bin" / "cc-switch"
    if kapsel_bin.is_file():
        return str(kapsel_bin)

    home = Path(os.environ.get("HOME", "/root"))
    candidates = [
        Path("/opt/homebrew/bin/cc-switch"),
        Path("/usr/local/bin/cc-switch"),
        Path("/usr/bin/cc-switch"),
        home / ".cargo/bin/cc-switch",
        home / ".local/bin/cc-switch",
    ]
    for cand in candidates:
        if cand.is_file():
            return str(cand)

    return None


class ProviderPlugin(KapselPlugin):
    """
    Provider Plugin for Kapsel.
    Direct transparent wrapper around SaladDay/cc-switch-cli (cc-switch).
    """

    manifest = PluginManifest(
        id="provider",
        name="Provider",
        version="0.1.0",
        description="AI model and API proxy switcher powered by cc-switch (SaladDay/cc-switch-cli).",
        author="MrEiu",
        homepage="https://github.com/SaladDay/cc-switch-cli",
        min_kapsel_version="0.1.0",
        dependencies=["cc-switch"],
        tags=["ai", "model", "provider", "claude-code", "cc-switch", "llm"],
    )

    def on_load(self, context: PluginContext) -> None:
        """Registers 'kps provider' command."""
        self.context = context
        self.console = Console(legacy_windows=False)
        context.register_kps_command(
            name="provider",
            handler=self.handle_command,
            help_text="AI model & API proxy switcher (powered by cc-switch-cli)",
            usage="kps provider [subcommand|flags] (runs interactive TUI when called with no arguments)",
            scope="feature",
        )

    def handle_command(self, args: List[str], console: Optional[Console] = None) -> int:
        """
        Executes cc-switch transparently with full TUI and TTY passthrough.
        """
        con = console or self.console or Console(legacy_windows=False)
        cc_bin = resolve_cc_switch_executable()

        if not cc_bin:
            con.print("\n[bold #f43f5e]Error:[/] [white]cc-switch executable not found.[/]")
            con.print("[dim]Upstream repository:[/] [cyan]https://github.com/SaladDay/cc-switch-cli[/]\n")

            # Try auto-installing via Kapsel Tool Installer
            try:
                from kapsel.core.tools.installer import install_tool
                con.print("[dim]Attempting automatic installation via Kapsel package installer...[/]")
                res = install_tool("cc-switch", console=con)
                if res.success and res.binary_path:
                    cc_bin = res.binary_path
                    con.print(f"[bold #10b981]✔ Successfully installed cc-switch: {cc_bin}[/]\n")
            except Exception as e:
                con.print(f"[dim]Auto-install failed: {e}[/]")

            if not cc_bin:
                con.print("[bold white]Installation options (macOS / Linux):[/]")
                con.print("  • Homebrew: [cyan]brew install cc-switch-cli[/]")
                con.print("  • Script:   [cyan]curl -fsSL https://raw.githubusercontent.com/SaladDay/cc-switch-cli/main/install.sh | bash[/]")
                con.print("  • Cargo:    [cyan]cargo install cc-switch-cli[/]")
                con.print("  • npm:      [cyan]npm install -g cc-switch-cli[/]\n")
                return 1

        try:
            # Full terminal passthrough (supports both interactive TUI and scriptable CLI)
            proc = subprocess.run([cc_bin] + args, shell=False)
            return proc.returncode
        except KeyboardInterrupt:
            return 130
        except Exception as e:
            con.print(f"[bold #f43f5e]Execution error:[/] {e}")
            return 1
