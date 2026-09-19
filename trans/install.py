"""
Installer and Dependency Checker for Translate Plugin.
On Windows: detects and installs 'fanyi' via npm/pnpm.
On macOS/Linux: detects and installs 'translate-shell' (or 'fanyi').
All comments and docstrings are in English.
"""

from pathlib import Path
import os
import shutil
import subprocess
import sys
from typing import Optional

from rich.console import Console

from .engine import resolve_translator_executable


def is_tool_installed() -> bool:
    """Checks if a valid translation engine (fanyi or translate-shell) is installed."""
    _, tool = resolve_translator_executable()
    return tool is not None


def print_installation_guide(console: Optional[Console] = None) -> None:
    """Prints platform-appropriate installation guidance."""
    con = console or Console()
    is_win = sys.platform == "win32"

    con.print("\n[bold #f43f5e]✖ Translation engine is not installed.[/]")
    if is_win:
        con.print("[dim]The 'trans' plugin uses 'fanyi' (Node.js) on Windows for native translation.[/]\n")
        con.print("[bold white]Recommended Installation Commands:[/]")
        con.print("  • [#38bdf8]npm:[/]   [bold green]npm install -g fanyi[/]")
        con.print("  • [#38bdf8]pnpm:[/]  [bold green]pnpm add -g fanyi[/]")
        con.print("  • [#38bdf8]yarn:[/]  [bold green]yarn global add fanyi[/]\n")
    else:
        con.print("[dim]The 'trans' plugin uses 'translate-shell' (or 'fanyi') for translation.[/]\n")
        con.print("[bold white]Recommended Installation Commands:[/]")
        con.print("  • [#38bdf8]Homebrew (macOS):[/] [bold green]brew install translate-shell[/]")
        con.print("  • [#38bdf8]APT (Debian/Ubuntu):[/] [bold green]sudo apt install translate-shell[/]")
        con.print("  • [#38bdf8]npm (Universal):[/]      [bold green]npm install -g fanyi[/]\n")


def auto_install(console: Optional[Console] = None) -> bool:
    """
    Attempts to auto-install the appropriate translation engine.
    Returns True if successfully installed.
    """
    con = console or Console()
    if is_tool_installed():
        con.print("[bold #10b981]✔ Translation engine is already installed and ready.[/]")
        return True

    is_win = sys.platform == "win32"

    if is_win:
        if shutil.which("npm"):
            con.print("[bold #38bdf8]⚡ Installing 'fanyi' globally via npm...[/]")
            res = subprocess.run(["npm", "install", "-g", "fanyi"])
            if res.returncode == 0:
                con.print("[bold #10b981]✔ Successfully installed 'fanyi' via npm![/]")
                return True
        elif shutil.which("pnpm"):
            con.print("[bold #38bdf8]⚡ Installing 'fanyi' globally via pnpm...[/]")
            res = subprocess.run(["pnpm", "add", "-g", "fanyi"])
            if res.returncode == 0:
                con.print("[bold #10b981]✔ Successfully installed 'fanyi' via pnpm![/]")
                return True
    else:
        if shutil.which("brew"):
            con.print("[bold #38bdf8]⚡ Installing translate-shell via Homebrew...[/]")
            res = subprocess.run(["brew", "install", "translate-shell"])
            if res.returncode == 0:
                con.print("[bold #10b981]✔ Successfully installed translate-shell via Homebrew![/]")
                return True
        elif shutil.which("npm"):
            con.print("[bold #38bdf8]⚡ Installing 'fanyi' via npm...[/]")
            res = subprocess.run(["npm", "install", "-g", "fanyi"])
            if res.returncode == 0:
                con.print("[bold #10b981]✔ Successfully installed 'fanyi' via npm![/]")
                return True

    print_installation_guide(con)
    return False


if __name__ == "__main__":
    auto_install()
