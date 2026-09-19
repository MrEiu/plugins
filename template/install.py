"""
Installer and Dependency Checker Reference for Kapsel Plugins.
Demonstrates how to detect third-party CLI tools and provide automated or manual
installation guidance across Windows, macOS, and Linux.
All comments and docstrings are in English.
"""

from pathlib import Path
import os
import shutil
import subprocess
import sys
from typing import Optional

from rich.console import Console

from .engine import resolve_tool_executable


# Name of the external tool binary required by this plugin (if any)
TARGET_TOOL_NAME = "example-tool"


def is_tool_installed() -> bool:
    """Checks if the required external CLI tool is installed on the system."""
    return resolve_tool_executable(TARGET_TOOL_NAME) is not None


def print_installation_guide(console: Optional[Console] = None) -> None:
    """Prints clear, actionable installation guidance across platforms."""
    con = console or Console()
    con.print(f"\n[bold #f43f5e]✖ Required tool '{TARGET_TOOL_NAME}' is not installed.[/]")
    con.print(f"[dim]Please install '{TARGET_TOOL_NAME}' using your preferred package manager:[/]\n")

    con.print("[bold white]Recommended Installation Commands:[/]")
    if sys.platform == "win32":
        con.print(f"  • [#38bdf8]Scoop:[/]  [bold green]scoop install {TARGET_TOOL_NAME}[/]")
        con.print(f"  • [#38bdf8]WinGet:[/] [bold green]winget install {TARGET_TOOL_NAME}[/]")
        con.print(f"  • [#38bdf8]Cargo:[/]  [bold green]cargo install {TARGET_TOOL_NAME}[/]\n")
    elif sys.platform == "darwin":
        con.print(f"  • [#38bdf8]Homebrew:[/] [bold green]brew install {TARGET_TOOL_NAME}[/]\n")
    else:
        con.print(f"  • [#38bdf8]Debian / Ubuntu:[/] [bold green]sudo apt install {TARGET_TOOL_NAME}[/]")
        con.print(f"  • [#38bdf8]Arch Linux:[/]      [bold green]sudo pacman -S {TARGET_TOOL_NAME}[/]")
        con.print(f"  • [#38bdf8]Fedora:[/]          [bold green]sudo dnf install {TARGET_TOOL_NAME}[/]\n")


def auto_install(console: Optional[Console] = None) -> bool:
    """
    Attempts to automatically install the required tool via host package manager.
    Returns True if successfully installed, False otherwise.
    """
    con = console or Console()
    if is_tool_installed():
        con.print(f"[bold #10b981]✔ '{TARGET_TOOL_NAME}' is already installed.[/]")
        return True

    # 1. Windows: probe scoop then winget
    if sys.platform == "win32":
        if shutil.which("scoop"):
            con.print(f"[bold #38bdf8]⚡ Installing '{TARGET_TOOL_NAME}' via Scoop...[/]")
            res = subprocess.run(["scoop", "install", TARGET_TOOL_NAME])
            if res.returncode == 0:
                con.print(f"[bold #10b981]✔ Successfully installed '{TARGET_TOOL_NAME}' via Scoop![/]")
                return True
        elif shutil.which("winget"):
            con.print(f"[bold #38bdf8]⚡ Installing '{TARGET_TOOL_NAME}' via WinGet...[/]")
            res = subprocess.run(["winget", "install", TARGET_TOOL_NAME, "--silent", "--accept-source-agreements"])
            if res.returncode == 0:
                con.print(f"[bold #10b981]✔ Successfully installed '{TARGET_TOOL_NAME}' via WinGet![/]")
                return True

    # 2. macOS: probe brew
    elif sys.platform == "darwin":
        if shutil.which("brew"):
            con.print(f"[bold #38bdf8]⚡ Installing '{TARGET_TOOL_NAME}' via Homebrew...[/]")
            res = subprocess.run(["brew", "install", TARGET_TOOL_NAME])
            if res.returncode == 0:
                con.print(f"[bold #10b981]✔ Successfully installed '{TARGET_TOOL_NAME}' via Homebrew![/]")
                return True

    # 3. Linux: probe apt
    else:
        if shutil.which("apt"):
            con.print(f"[bold #38bdf8]⚡ Installing '{TARGET_TOOL_NAME}' via APT...[/]")
            res = subprocess.run(["sudo", "apt", "install", "-y", TARGET_TOOL_NAME])
            if res.returncode == 0:
                con.print(f"[bold #10b981]✔ Successfully installed '{TARGET_TOOL_NAME}' via APT![/]")
                return True

    print_installation_guide(con)
    return False


if __name__ == "__main__":
    auto_install()
