"""
Installer for preview plugin.
Checks and installs dedicated CLI tools across platforms (Scoop, WinGet, Homebrew, Cargo):
1. Code & Text:       bat
2. Markdown:          glow
3. Structured Data:   jq
4. Tabular Data:      xsv
5. Directory Trees:   eza / tree
6. Archives:          7z / tar
7. Terminal Images:   chafa
8. PDF Documents:     pdf-cli
9. Media Metadata:    mediainfo / ffprobe
10. Hex / Binaries:   xxd / hexdump

All comments and descriptions are in English.
"""

from pathlib import Path
import os
import shutil
import subprocess
import sys
from typing import Dict, List, Optional, Tuple

from rich.console import Console
from rich.table import Table


TOOLS_MANIFEST: List[Dict[str, str]] = [
    {
        "name": "bat",
        "category": "Code & Text",
        "scoop": "bat",
        "winget": "sharkdp.bat",
        "brew": "bat",
        "cargo": "bat",
    },
    {
        "name": "glow",
        "category": "Markdown",
        "scoop": "glow",
        "winget": "Charmbracelet.Glow",
        "brew": "glow",
        "cargo": "",
    },
    {
        "name": "jq",
        "category": "Structured (JSON)",
        "scoop": "jq",
        "winget": "jqlang.jq",
        "brew": "jq",
        "cargo": "",
    },
    {
        "name": "xsv",
        "category": "Tabular (CSV/TSV)",
        "scoop": "xsv",
        "winget": "",
        "brew": "xsv",
        "cargo": "xsv",
    },
    {
        "name": "eza",
        "category": "Directories",
        "scoop": "eza",
        "winget": "eza-community.eza",
        "brew": "eza",
        "cargo": "eza",
    },
    {
        "name": "7z",
        "category": "Archives",
        "scoop": "7zip",
        "winget": "7zip.7zip",
        "brew": "sevenzip",
        "cargo": "",
    },
    {
        "name": "chafa",
        "category": "Terminal Images",
        "scoop": "chafa",
        "winget": "",
        "brew": "chafa",
        "cargo": "",
    },
    {
        "name": "pdf-cli",
        "category": "PDF Documents",
        "scoop": "poppler",
        "winget": "",
        "brew": "poppler",
        "cargo": "pdf-cli",
    },
    {
        "name": "mediainfo",
        "category": "Media Metadata",
        "scoop": "mediainfo",
        "winget": "MediaArea.MediaInfo.CLI",
        "brew": "mediainfo",
        "cargo": "",
    },
    {
        "name": "xxd",
        "category": "Hex / Binaries",
        "scoop": "vim",
        "winget": "",
        "brew": "xxd",
        "cargo": "",
    },
]


def _check_tool(name: str, bin_dir: Path) -> Optional[str]:
    """Checks if a tool is available in PATH, bin_dir, Scoop, or WinGet."""
    p = shutil.which(name)
    if p:
        return p

    is_win = sys.platform == "win32"
    exe_name = f"{name}.exe" if is_win else name
    local_p = bin_dir / exe_name
    if local_p.exists():
        return str(local_p)

    if is_win:
        user_home = Path(os.environ.get("USERPROFILE", Path.home()))
        candidates = [
            user_home / "scoop" / "shims" / exe_name,
            user_home / "scoop" / "apps" / name / "current" / exe_name,
            user_home / "AppData" / "Local" / "Microsoft" / "WinGet" / "Links" / exe_name,
            user_home / ".cargo" / "bin" / exe_name,
        ]
        for cand in candidates:
            if cand.exists():
                return str(cand)
    else:
        user_home = Path(os.environ.get("HOME", Path.home()))
        unix_candidates = [
            Path("/opt/homebrew/bin") / exe_name,
            Path("/usr/local/bin") / exe_name,
            Path("/usr/bin") / exe_name,
            user_home / ".cargo" / "bin" / exe_name,
        ]
        for cand in unix_candidates:
            if cand.exists():
                return str(cand)

    # Fallback tool alternatives
    if name == "eza" and shutil.which("tree"):
        return shutil.which("tree")
    if name == "7z" and shutil.which("tar"):
        return shutil.which("tar")
    if name == "mediainfo" and shutil.which("ffprobe"):
        return shutil.which("ffprobe")
    if name == "xxd" and shutil.which("hexdump"):
        return shutil.which("hexdump")
    if name == "pdf-cli" and shutil.which("pdftotext"):
        return shutil.which("pdftotext")

    return None


def _try_install_tool(manifest_entry: Dict[str, str], console: Console) -> bool:
    """Attempts to install a missing tool using available system package managers."""
    name = manifest_entry["name"]
    is_win = sys.platform == "win32"
    is_mac = sys.platform == "darwin"
    is_linux = sys.platform.startswith("linux")

    # 1. Windows Scoop
    if is_win and shutil.which("scoop") and manifest_entry.get("scoop"):
        pkg = manifest_entry["scoop"]
        try:
            res = subprocess.run(["scoop", "install", pkg], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=90)
            if res.returncode == 0:
                return True
        except Exception:
            pass

    # 2. Windows WinGet
    if is_win and shutil.which("winget") and manifest_entry.get("winget"):
        pkg = manifest_entry["winget"]
        try:
            res = subprocess.run(
                ["winget", "install", "--id", pkg, "-e", "--silent", "--accept-source-agreements", "--accept-package-agreements"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=90,
            )
            if res.returncode == 0:
                return True
        except Exception:
            pass

    # 3. macOS / Linux Homebrew
    if (is_mac or is_linux) and shutil.which("brew") and manifest_entry.get("brew"):
        pkg = manifest_entry["brew"]
        try:
            res = subprocess.run(["brew", "install", pkg], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
            if res.returncode == 0:
                return True
        except Exception:
            pass

    # 4. Cargo (Rust) fallback
    if shutil.which("cargo") and manifest_entry.get("cargo"):
        pkg = manifest_entry["cargo"]
        try:
            res = subprocess.run(["cargo", "install", pkg], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=180)
            if res.returncode == 0:
                return True
        except Exception:
            pass

    return False


def install(console: Console, bin_dir: Path) -> bool:
    """
    Installs and verifies dedicated CLI preview tools.
    Renders an informative status table of all 10 preview categories.
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
            # Attempt automatic install
            console.print(f"[dim]  Attempting to install {name}...[/]")
            if _try_install_tool(item, console):
                found = _check_tool(name, bin_dir)

        if found:
            installed_count += 1
            table.add_row(cat, name, "[bold #10b981]✔ Installed[/]", f"{found}")
        else:
            hint = f"scoop install {item.get('scoop', name)}" if sys.platform == "win32" else f"brew install {item.get('brew', name)}"
            table.add_row(cat, name, "[bold #f43f5e]✘ Missing[/]", f"{hint}")

    console.print(table)
    console.print(f"\n[bold]{installed_count}/{len(TOOLS_MANIFEST)}[/] preview power tools ready.")

    if installed_count == 0:
        console.print("[bold #f43f5e]Warning:[/] No dedicated preview tools installed yet.")
        console.print("[dim]You can install tools individually, e.g.: 'scoop install bat glow jq xsv eza pdf-cli'[/]\n")
    else:
        console.print("[bold #10b981]✔ Preview dispatcher initialized successfully![/]\n")

    return True
