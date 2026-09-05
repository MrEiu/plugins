"""
Installer for shore (chsrc mirror source switcher) plugin.
Installs chsrc across platforms via package managers (Scoop, WinGet, Homebrew)
or standalone prebuilt binary from GitHub Releases.
All comments and descriptions are in English.
"""

from pathlib import Path
import os
import platform
import shutil
import subprocess
import sys
import urllib.request
from rich.console import Console


def install(console: Console, bin_dir: Path) -> bool:
    """
    Installs chsrc CLI across platforms:
    1. Check if chsrc already exists in PATH, Scoop, WinGet, or bin_dir
    2. Try kps install chsrc
    3. Try native package managers: Scoop / WinGet (Windows), Homebrew (macOS/Linux)
    4. Fallback: Direct standalone binary download from GitHub Releases to bin_dir
    """
    bin_dir.mkdir(parents=True, exist_ok=True)
    is_win = sys.platform == "win32"
    local_chsrc = bin_dir / ("chsrc.exe" if is_win else "chsrc")

    if shutil.which("chsrc") or local_chsrc.exists():
        console.print("[dim]✔ chsrc is already installed in PATH or Kapsel bin.[/]")
        return True

    # Check Windows common Scoop / WinGet paths
    if is_win:
        user_home = Path(os.environ.get("USERPROFILE", Path.home()))
        for candidate in [
            user_home / "scoop/shims/chsrc.exe",
            user_home / "scoop/apps/chsrc/current/chsrc.exe",
            user_home / "AppData/Local/Microsoft/WinGet/Links/chsrc.exe",
        ]:
            if candidate.exists():
                console.print(f"[dim]✔ chsrc found at {candidate}[/]")
                return True

    system_name = platform.system().lower()
    console.print(f"[bold #00f0ff]📦 Installing chsrc for platform: {system_name}...[/]")

    # 1. Try unified package manager (kps install)
    if shutil.which("kps"):
        try:
            res = subprocess.run(["kps", "install", "chsrc"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
            if res.returncode == 0 and shutil.which("chsrc"):
                console.print("[bold #10b981]✔ chsrc successfully installed via kps install![/]")
                return True
        except Exception:
            pass

    # 2. Windows: Scoop / Winget
    if is_win:
        if shutil.which("scoop"):
            try:
                console.print("[dim]  Attempting installation via Scoop...[/]")
                res = subprocess.run(["scoop", "install", "chsrc"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=90)
                if res.returncode == 0 and shutil.which("chsrc"):
                    console.print("[bold #10b981]✔ chsrc installed via Scoop![/]")
                    return True
            except Exception:
                pass

        if shutil.which("winget"):
            try:
                console.print("[dim]  Attempting installation via WinGet...[/]")
                res = subprocess.run(
                    ["winget", "install", "--id", "RubyMetric.chsrc", "-e", "--silent", "--accept-source-agreements", "--accept-package-agreements"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=90,
                )
                if res.returncode == 0 and shutil.which("chsrc"):
                    console.print("[bold #10b981]✔ chsrc installed via WinGet![/]")
                    return True
            except Exception:
                pass

    # 3. macOS / Linux: Homebrew
    if (sys.platform == "darwin" or sys.platform.startswith("linux")) and shutil.which("brew"):
        try:
            console.print("[dim]  Attempting installation via Homebrew...[/]")
            res = subprocess.run(["brew", "install", "chsrc"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
            if res.returncode == 0 and shutil.which("chsrc"):
                console.print("[bold #10b981]✔ chsrc installed via Homebrew![/]")
                return True
        except Exception:
            pass

    # 4. Fallback: Direct standalone binary download from GitHub Releases
    try:
        console.print("[dim]  Downloading standalone prebuilt chsrc binary from GitHub Releases...[/]")
        machine = platform.machine().lower()
        is_arm = "arm" in machine or "aarch64" in machine

        if is_win:
            arch = "arm64" if is_arm else "x64"
            url = f"https://github.com/RubyMetric/chsrc/releases/latest/download/chsrc-windows-{arch}.exe"
        elif sys.platform == "darwin":
            arch = "arm64" if is_arm else "x64"
            url = f"https://github.com/RubyMetric/chsrc/releases/latest/download/chsrc-macos-{arch}"
        elif sys.platform.startswith("linux"):
            arch = "aarch64" if is_arm else "x64"
            url = f"https://github.com/RubyMetric/chsrc/releases/latest/download/chsrc-linux-{arch}"
        else:
            url = None

        if url:
            urllib.request.urlretrieve(url, local_chsrc)
            if not is_win:
                local_chsrc.chmod(0o755)
            if local_chsrc.exists():
                console.print(f"[bold #10b981]✔ Standalone binary installed to {local_chsrc}[/]")
                return True
    except Exception as e:
        console.print(f"[yellow]  Standalone download fallback failed:[/] {e}")

    return bool(shutil.which("chsrc") or local_chsrc.exists())
