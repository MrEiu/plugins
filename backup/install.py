"""
Installer and Dependency Checker for Backup Plugin.
Installs 'gitkeep-cli' globally via npm, pnpm, bun, or yarn.
All comments and docstrings are in English.
"""

from pathlib import Path
import os
import shutil
import subprocess
import sys
from typing import Optional, Tuple

from rich.console import Console

try:
    from .engine import resolve_bk_command
except ImportError:
    from plugins.backup.engine import resolve_bk_command


NPM_PACKAGE_NAME = "gitkeep-cli"


def is_tool_installed() -> bool:
    """Checks if 'bk' or 'gitkeep' executable is available."""
    cmd = resolve_bk_command()
    return cmd is not None


def print_installation_guide(console: Optional[Console] = None) -> None:
    """Prints friendly installation instructions for gitkeep-cli."""
    con = console or Console(legacy_windows=False)
    con.print("\n[bold #f43f5e]✖ GitKeep CLI engine (bk) is not installed.[/]")
    con.print(f"[dim]The backup plugin relies on '[bold white]{NPM_PACKAGE_NAME}[/]' to provide zero-pollution backups.[/]\n")
    con.print("[bold white]Recommended Installation Commands:[/]")
    con.print(f"  • [#38bdf8]npm:[/]   [bold green]npm install -g {NPM_PACKAGE_NAME}[/]")
    con.print(f"  • [#38bdf8]pnpm:[/]  [bold green]pnpm add -g {NPM_PACKAGE_NAME}[/]")
    con.print(f"  • [#38bdf8]bun:[/]   [bold green]bun add -g {NPM_PACKAGE_NAME}[/]")
    con.print(f"  • [#38bdf8]yarn:[/]  [bold green]yarn global add {NPM_PACKAGE_NAME}[/]\n")


def auto_install(console: Optional[Console] = None) -> bool:
    """
    Attempts to auto-install 'gitkeep-cli' globally using the first available package manager.
    Priority: npm -> pnpm -> bun -> yarn.
    Returns True if successfully installed.
    """
    con = console or Console(legacy_windows=False)
    if is_tool_installed():
        con.print("[bold #10b981]✔ GitKeep CLI is already installed and ready.[/]")
        return True

    managers = [
        ("npm", ["npm", "install", "-g", NPM_PACKAGE_NAME]),
        ("pnpm", ["pnpm", "add", "-g", NPM_PACKAGE_NAME]),
        ("bun", ["bun", "add", "-g", NPM_PACKAGE_NAME]),
        ("yarn", ["yarn", "global", "add", NPM_PACKAGE_NAME]),
    ]

    for mgr_name, cmd in managers:
        if shutil.which(mgr_name):
            con.print(f"[bold #38bdf8]⚡ Installing '{NPM_PACKAGE_NAME}' globally via {mgr_name}...[/]")
            try:
                res = subprocess.run(cmd, check=False)
                if res.returncode == 0:
                    con.print(f"[bold #10b981]✔ Successfully installed '{NPM_PACKAGE_NAME}' via {mgr_name}![/]")
                    return True
                else:
                    con.print(f"[yellow]⚠ {mgr_name} exited with code {res.returncode}, trying next...[/yellow]")
            except Exception as e:
                con.print(f"[yellow]⚠ Failed to execute {mgr_name}: {e}[/yellow]")

    print_installation_guide(con)
    return False


if __name__ == "__main__":
    auto_install()
