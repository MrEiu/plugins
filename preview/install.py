"""
Compatibility adapter and installer for preview plugin.
Delegates to declarative tools.yaml and kapsel.core.tools.
All comments and descriptions are in English.
"""

from pathlib import Path
import shutil
import sys
from typing import Dict, List, Optional
from rich.console import Console
from rich.table import Table

from kapsel.core.tools.installer import is_tool_installed, install_tool, resolve_tool_executable
from kapsel.core.tools.registry import get_plugin_tools


TOOLS_MANIFEST: List[Dict[str, str]] = [
    {"name": "bat", "category": "Code & Text", "scoop": "bat", "winget": "sharkdp.bat", "brew": "bat", "cargo": "bat"},
    {"name": "glow", "category": "Markdown", "scoop": "glow", "winget": "Charmbracelet.Glow", "brew": "glow", "cargo": ""},
    {"name": "jq", "category": "Structured (JSON)", "scoop": "jq", "winget": "jqlang.jq", "brew": "jq", "cargo": ""},
    {"name": "xsv", "category": "Tabular (CSV/TSV)", "scoop": "xsv", "winget": "", "brew": "xsv", "cargo": "xsv"},
    {"name": "eza", "category": "Directories", "scoop": "eza", "winget": "eza-community.eza", "brew": "eza", "cargo": "eza"},
    {"name": "7z", "category": "Archives", "scoop": "7zip", "winget": "7zip.7zip", "brew": "sevenzip", "cargo": ""},
    {"name": "chafa", "category": "Terminal Images", "scoop": "chafa", "winget": "", "brew": "chafa", "cargo": ""},
    {"name": "pdf-cli", "category": "PDF Documents", "scoop": "poppler", "winget": "", "brew": "poppler", "cargo": "pdf-cli"},
    {"name": "mediainfo", "category": "Media Metadata", "scoop": "mediainfo", "winget": "MediaArea.MediaInfo.CLI", "brew": "mediainfo", "cargo": ""},
    {"name": "xxd", "category": "Hex / Binaries", "scoop": "vim", "winget": "", "brew": "xxd", "cargo": ""},
]


def _try_install_tool(item: Dict[str, str], console: Console) -> bool:
    """Attempts to install a tool using core declarative installer."""
    return install_tool(item["name"], console=console)


def _check_tool(name: str, bin_dir: Path) -> Optional[str]:
    """Checks if a preview tool is installed."""
    return resolve_tool_executable(name, bin_dir=bin_dir)


def install(console: Console, bin_dir: Path) -> bool:
    """
    Installs and verifies dedicated CLI preview tools.
    Renders an informative status table of preview categories.
    """
    bin_dir.mkdir(parents=True, exist_ok=True)
    console.print("\n[bold #00f0ff]🔍 Scanning Preview CLI Power Tools Matrix...[/]\n")

    table = Table(box=None, header_style="bold #38bdf8")
    table.add_column("Category", style="cyan")
    table.add_column("Tool", style="bold white")
    table.add_column("Status")
    table.add_column("Location / Install Command", style="dim")

    installed_count = 0

    for item in TOOLS_MANIFEST:
        name = item["name"]
        cat = item["category"]
        found = _check_tool(name, bin_dir)

        if not found:
            _try_install_tool(item, console)
            found = _check_tool(name, bin_dir)

        if found:
            installed_count += 1
            table.add_row(cat, name, "[bold #10b981]✔ Installed[/]", f"{found}")
        else:
            hint = f"scoop install {item.get('scoop', name)}" if sys.platform == "win32" else f"brew install {item.get('brew', name)}"
            table.add_row(cat, name, "[bold #f43f5e]✘ Missing[/]", f"{hint}")

    console.print(table)
    console.print(f"\n[bold]{installed_count}/{len(TOOLS_MANIFEST)}[/] preview power tools ready.")
    return True
