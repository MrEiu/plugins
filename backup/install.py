"""
Installer adapter for backup plugin.
Delegates to declarative tools.yaml and kapsel.core.tools.
All comments and descriptions are in English.
"""

from pathlib import Path
from typing import Optional
from rich.console import Console

from kapsel.core.tools.installer import install_tool, is_tool_installed, ToolInstaller


def is_installed(bin_dir: Optional[Path] = None) -> bool:
    """Checks if gitkeep-cli / bk is installed."""
    return is_tool_installed("gitkeep-cli", bin_dir=bin_dir)


def print_installation_guide(console: Optional[Console] = None) -> None:
    """Prints manual installation tips for gitkeep-cli."""
    ToolInstaller(console).print_tool_guide("gitkeep-cli")


def auto_install(console: Optional[Console] = None, bin_dir: Optional[Path] = None) -> bool:
    """Automatically installs gitkeep-cli via npm using core installer."""
    return install_tool("gitkeep-cli", console=console, bin_dir=bin_dir)


def install(console: Console, bin_dir: Path) -> bool:
    """Standard Kapsel plugin installer entry point."""
    return auto_install(console, bin_dir)
