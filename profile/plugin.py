"""
Profile Plugin for Kapsel.
Bridges the 'chezmoi' CLI tool to provide cross-platform dotfile and shell profile management.
Exposes functional commands under the 'kps profile' namespace.
All comments and descriptions are in English.
"""

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


def _resolve_chezmoi_executable() -> Optional[str]:
    """
    Locates the chezmoi CLI executable.
    Checks system PATH first, then Kapsel local bin directory (~/.kapsel/bin).
    """
    # 1. System PATH
    chezmoi_path = shutil.which("chezmoi")
    if chezmoi_path:
        return chezmoi_path

    # 2. Local Kapsel bin directory (~/.kapsel/bin/chezmoi.exe or chezmoi)
    bin_dir = get_kapsel_dir() / "bin"
    local_chezmoi = bin_dir / ("chezmoi.exe" if sys.platform == "win32" else "chezmoi")
    if local_chezmoi.exists():
        return str(local_chezmoi)

    return None


def _run_chezmoi_command(args: List[str], console: Optional[Console] = None) -> int:
    """
    Executes a chezmoi command with forwarded arguments.
    Prompts user with installation instructions if chezmoi is not found.
    """
    con = console or Console(legacy_windows=False)
    chezmoi_bin = _resolve_chezmoi_executable()

    if not chezmoi_bin:
        con.print("[bold #f43f5e]Error:[/] [white]chezmoi (dotfile manager) is not installed.[/]")
        con.print("[dim]To install chezmoi, run:[/] [bold #00f0ff]kapsel add profile[/]\n")
        return 1

    cmd = [chezmoi_bin] + args
    try:
        # Stream interactive execution to terminal
        result = subprocess.run(cmd)
        return result.returncode
    except Exception as e:
        con.print(f"[bold #f43f5e]Failed to execute chezmoi:[/] {e}")
        return 1


class ProfilePlugin(KapselPlugin):
    """
    Kapsel 'profile' plugin integrating chezmoi for dotfiles and shell profile synchronization.
    """

    manifest = PluginManifest(
        id="profile",
        name="Profile",
        version="0.1.0",
        description="Cross-platform dotfile and shell profile manager powered by chezmoi.",
        author="Kapsel Team",
        homepage="https://github.com/MrEiu/plugins/tree/master/profile",
        min_kapsel_version="0.1.0",
        dependencies=["chezmoi"],
        tags=["dotfiles", "profile", "chezmoi", "config", "sync"],
    )

    def on_load(self, context: PluginContext) -> None:
        """Registers the 'profile' functional command under the 'kps' scope."""
        context.register_kps_command(
            name="profile",
            handler=self.handle_profile,
            help_text="Dotfile & configuration manager powered by chezmoi (init, apply, diff, add)",
            usage="kps profile [init|apply|add|status|diff|update|edit|cd] [options]",
            scope="feature",
        )

    def handle_profile(self, args: List[str], console: Optional[Console] = None) -> int:
        """
        Dispatches 'kps profile' subcommands:
        - 'kps profile init [user/repo]' -> chezmoi init
        - 'kps profile apply'            -> chezmoi apply
        - 'kps profile add <path>'       -> chezmoi add <path>
        - 'kps profile status'           -> chezmoi status
        - 'kps profile diff'             -> chezmoi diff
        - 'kps profile update'           -> chezmoi update
        - 'kps profile edit <file>'      -> chezmoi edit <file>
        - 'kps profile cd'               -> chezmoi cd
        """
        con = console or Console(legacy_windows=False)

        if not args:
            # Default to checking status if initialized, else show help
            con.print("\n[bold #00f0ff]● Kapsel Profile Status (chezmoi)[/]\n")
            res = _run_chezmoi_command(["status"], con)
            if res != 0:
                con.print("[dim]Use 'kps profile --help' to inspect available profile commands.[/]\n")
            return res

        subcmd = args[0].lower()
        sub_args = args[1:]

        if subcmd in ("-h", "--help", "help"):
            con.print("\n[bold #00f0ff]● Kapsel Profile Plugin (Dotfile & Environment Manager)[/]")
            con.print("[dim]Powered by chezmoi (https://www.chezmoi.io)[/]\n")
            con.print("[bold white]Usage:[/]")
            con.print("  [bold #a855f7]kps profile init <repo>[/]      Initialize profile from GitHub dotfiles repository")
            con.print("  [bold #a855f7]kps profile apply[/]            Apply dotfile configurations to host system")
            con.print("  [bold #a855f7]kps profile add <file>[/]       Track a new configuration file (e.g. ~/.gitconfig)")
            con.print("  [bold #a855f7]kps profile status[/]           Inspect status of tracked configuration files")
            con.print("  [bold #a855f7]kps profile diff[/]             Show diff between target system and profile state")
            con.print("  [bold #a855f7]kps profile update[/]           Pull latest changes from git and apply")
            con.print("  [bold #a855f7]kps profile edit <file>[/]      Edit a managed configuration file")
            con.print("  [bold #a855f7]kps profile cd[/]               Open a shell inside the dotfiles repository\n")
            return 0

        # Direct passthrough to chezmoi subcommands
        return _run_chezmoi_command([subcmd] + sub_args, con)
