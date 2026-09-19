"""
Installer adapter for trans plugin.
Delegates to declarative tools.yaml and kapsel.core.tools.
All comments and descriptions are in English.
"""

from pathlib import Path
import sys
from typing import Optional
from rich.console import Console

from kapsel.core.tools.installer import ToolInstaller, install_plugin_tools


def print_installation_guide(console: Optional[Console] = None) -> None:
    """Prints manual installation tips for fanyi / translate-shell."""
    con = console or Console()
    tool = "fanyi" if sys.platform == "win32" else "translate-shell"
    ToolInstaller(con).print_tool_guide(tool)


def auto_install(console: Optional[Console] = None, bin_dir: Optional[Path] = None) -> bool:
    """Installs translation tools using core installer."""
    plugin_dir = Path(__file__).resolve().parent
    return install_plugin_tools(plugin_dir, console=console, bin_dir=bin_dir)


def install(console: Console, bin_dir: Path) -> bool:
    """Standard Kapsel plugin installer entry point."""
    return auto_install(console, bin_dir)
