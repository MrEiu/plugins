"""
Install Plugin for Kapsel.
Bridges meta-package-manager (mpm) to provide unified cross-platform package operations.
Exposes functional commands under the 'kps' command prefix.
All comments and descriptions are in English.
"""

import shutil
import subprocess
import sys
from typing import List, Optional
from rich.console import Console

from kapsel.core.plugin.base import KapselPlugin, PluginManifest
from kapsel.core.plugin.context import PluginContext


def _resolve_mpm_executable() -> Optional[List[str]]:
    """
    Locates the meta-package-manager (mpm) CLI executable.
    Checks PATH first, then falls back to python module execution.
    """
    mpm_path = shutil.which("mpm")
    if mpm_path:
        return [mpm_path]

    # Check if meta_package_manager is installed in Python environment
    try:
        res = subprocess.run(
            [sys.executable, "-m", "meta_package_manager", "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,
        )
        if res.returncode == 0:
            return [sys.executable, "-m", "meta_package_manager"]
    except Exception:
        pass

    return None


def _run_mpm_command(subcmd: str, args: List[str], console: Optional[Console] = None) -> int:
    """
    Executes an MPM subcommand with forwarded arguments.
    Prompts the user to install meta-package-manager if not found.
    """
    con = console or Console(legacy_windows=False)
    mpm_exec = _resolve_mpm_executable()

    if not mpm_exec:
        con.print("[bold #f43f5e]Error:[/] [white]meta-package-manager (mpm) is not installed.[/]")
        con.print("[dim]To enable cross-platform package management, install it via pip:[/]")
        con.print("    [bold #00f0ff]pip install meta-package-manager[/]\n")
        return 1

    cmd = mpm_exec + [subcmd] + args
    try:
        # Stream process execution interactively to the terminal
        result = subprocess.run(cmd)
        return result.returncode
    except Exception as e:
        con.print(f"[bold #f43f5e]Failed to execute mpm {subcmd}:[/] {e}")
        return 1


class InstallPlugin(KapselPlugin):
    """
    Kapsel 'install' plugin integrating meta-package-manager.
    Provides unified package installation, updating, searching, and syncing under the 'kps' scope.
    """

    manifest = PluginManifest(
        id="install",
        name="Install",
        version="0.1.0",
        description="Unified cross-platform package installer powered by meta-package-manager (mpm).",
        author="Kapsel Team",
        homepage="https://github.com/kapsel-shell/kapsel-plugin-install",
        min_kapsel_version="0.1.0",
        dependencies=["meta-package-manager"],
        tags=["package-manager", "installer", "tools"],
    )

    def on_load(self, context: PluginContext) -> None:
        """Registers mpm-backed functional commands under the 'kps' scope."""

        # 1. kps install <package>
        context.register_kps_command(
            name="install",
            handler=self.handle_install,
            help_text="Install package(s) across systems using meta-package-manager",
            usage="kps install <package_name> [options]",
            scope="feature",
        )

        # 2. kps update [package]
        context.register_kps_command(
            name="update",
            handler=self.handle_update,
            help_text="Update installed packages across package managers",
            usage="kps update [package_name] [options]",
            scope="feature",
        )

        # 3. kps search <query>
        context.register_kps_command(
            name="search",
            handler=self.handle_search,
            help_text="Search for packages across package managers",
            usage="kps search <query> [options]",
            scope="feature",
        )

        # 4. kps sync -mpm [options]
        context.register_kps_command(
            name="sync",
            handler=self.handle_sync,
            help_text="Synchronize package configurations (use -mpm for meta-package-manager)",
            subcommands={
                "-mpm": "Sync package manager configurations via mpm",
                "--mpm": "Sync package manager configurations via mpm",
            },
            usage="kps sync -mpm [options]",
            scope="feature",
        )

    def handle_install(self, args: List[str], console: Optional[Console] = None) -> int:
        """Handles 'kps install'."""
        con = console or Console(legacy_windows=False)
        if not args:
            con.print("[bold #f43f5e]Error:[/] Please specify package name(s) to install.")
            con.print("[dim]Usage: kps install <package_name>[/]")
            return 1
        return _run_mpm_command("install", args, con)

    def handle_update(self, args: List[str], console: Optional[Console] = None) -> int:
        """Handles 'kps update'."""
        return _run_mpm_command("update", args, console)

    def handle_search(self, args: List[str], console: Optional[Console] = None) -> int:
        """Handles 'kps search'."""
        con = console or Console(legacy_windows=False)
        if not args:
            con.print("[bold #f43f5e]Error:[/] Please specify a search query.")
            con.print("[dim]Usage: kps search <query>[/]")
            return 1
        return _run_mpm_command("search", args, con)

    def handle_sync(self, args: List[str], console: Optional[Console] = None) -> int:
        """
        Handles 'kps sync'.
        Requires '-mpm' or '--mpm' flag to trigger MPM sync, reserving bare 'sync' for future cloud roaming.
        """
        con = console or Console(legacy_windows=False)

        # Check for -mpm or --mpm flag
        has_mpm_flag = any(arg in ("-mpm", "--mpm") for arg in args)

        if has_mpm_flag:
            # Strip -mpm flag and pass remaining arguments to mpm sync
            forwarded_args = [arg for arg in args if arg not in ("-mpm", "--mpm")]
            return _run_mpm_command("sync", forwarded_args, con)

        # If -mpm flag is missing, explain reservation for cloud sync
        con.print("[bold #f59e0b]Notice:[/] General cloud synchronization is reserved for future releases.")
        con.print("To synchronize package manager configurations via MPM, please add the [bold #00f0ff]-mpm[/] flag:")
        con.print("    [bold #00f0ff]kps sync -mpm[/] [dim][options][/]\n")
        return 0
