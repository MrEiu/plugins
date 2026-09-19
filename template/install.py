"""
Installer adapter reference for template plugin.
Delegates to declarative tools.yaml and kapsel.core.tools.
All comments and descriptions are in English.
"""

from pathlib import Path
from typing import Optional
from rich.console import Console

from kapsel.core.tools.installer import is_tool_installed as core_is_installed, ToolInstaller


TARGET_TOOL_NAME = "example-tool"


def is_tool_installed() -> bool:
    """Checks if the required external CLI tool is installed."""
    return core_is_installed(TARGET_TOOL_NAME)


def print_installation_guide(console: Optional[Console] = None) -> None:
    """Prints installation guide."""
    con = console or Console()
    con.print(f"[dim]Template plugin reference tool: {TARGET_TOOL_NAME}[/]")


def auto_install(console: Optional[Console] = None) -> bool:
    """Auto install placeholder."""
    return True


def install(console: Console, bin_dir: Path) -> bool:
    """Standard Kapsel plugin installer entry point."""
    return auto_install(console)
