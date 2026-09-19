"""
Installer adapter for help plugin.
Delegates to declarative tools.yaml and kapsel.core.tools.
All comments and descriptions are in English.
"""

from pathlib import Path
from rich.console import Console
from kapsel.core.tools.installer import install_plugin_tools


def install_recommended_tools(console: Console, bin_dir: Path) -> bool:
    """Installs all recommended external diagnostics tools declared in help/tools.yaml."""
    plugin_dir = Path(__file__).resolve().parent
    return install_plugin_tools(plugin_dir, console=console, bin_dir=bin_dir)


def install(console: Console, bin_dir: Path) -> bool:
    """Standard Kapsel plugin installer entry point."""
    return install_recommended_tools(console, bin_dir)
