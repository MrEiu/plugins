"""
Installer for help (tealdeer / tldr) plugin.
Installs tealdeer across platforms via package managers or standalone binaries,
and initializes local page cache.
All comments and descriptions are in English.
"""

from pathlib import Path
import platform
import shutil
import subprocess
import sys
from typing import Optional
import urllib.request
from rich.console import Console


def install(console: Console, bin_dir: Path) -> bool:
    """
    Installs tealdeer CLI across platforms:
    1. Check if tldr or tealdeer already exists in PATH or bin_dir
    2. Try kps install tealdeer
    3. Try native package managers: Scoop / Winget (Windows), Homebrew (macOS/Linux)
    4. Fallback: Direct official standalone binary download from GitHub Releases to bin_dir
    5. Automatically runs 'tldr --update' to initialize cheat sheet cache
    """
    bin_dir.mkdir(parents=True, exist_ok=True)
    is_win = sys.platform == "win32"
    local_tldr = bin_dir / ("tldr.exe" if is_win else "tldr")

    if shutil.which("tldr") or shutil.which("tealdeer") or local_tldr.exists():
        console.print("[dim]✔ tealdeer (tldr) is already installed.[/]")
        return True

    system_name = platform.system().lower()
    console.print(f"[bold #00f0ff]📦 Installing tealdeer (tldr) for platform: {system_name}...[/]")

    # 1. Try unified package manager (kps install)
    if shutil.which("kps"):
        try:
            res = subprocess.run(["kps", "install", "tealdeer"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
            if res.returncode == 0 and (shutil.which("tldr") or shutil.which("tealdeer")):
                _init_cache(console)
                return True
        except Exception:
            pass

    # 2. Platform-specific: macOS / Linux (Homebrew)
    if (sys.platform == "darwin" or sys.platform.startswith("linux")) and shutil.which("brew"):
        try:
            console.print("[dim]  Attempting installation via Homebrew...[/]")
            res = subprocess.run(["brew", "install", "tealdeer"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
            if res.returncode == 0 and (shutil.which("tldr") or shutil.which("tealdeer")):
                _init_cache(console)
                return True
        except Exception:
            pass

    # 3. Platform-specific: Windows (Scoop / Winget)
    if is_win:
        if shutil.which("scoop"):
            try:
                console.print("[dim]  Attempting installation via Scoop...[/]")
                res = subprocess.run(["scoop", "install", "tealdeer"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=90)
                if res.returncode == 0 and (shutil.which("tldr") or shutil.which("tealdeer")):
                    _init_cache(console)
                    return True
            except Exception:
                pass
        if shutil.which("winget"):
            try:
                console.print("[dim]  Attempting installation via WinGet...[/]")
                res = subprocess.run(
                    ["winget", "install", "--id", "dbrgn.tealdeer", "-e", "--silent", "--accept-source-agreements", "--accept-package-agreements"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=90,
                )
                if res.returncode == 0 and (shutil.which("tldr") or shutil.which("tealdeer")):
                    _init_cache(console)
                    return True
            except Exception:
                pass

    # 4. Fallback: Direct official standalone binary download from GitHub Releases
    try:
        console.print("[dim]  Downloading standalone tealdeer binary from GitHub Releases...[/]")
        machine = platform.machine().lower()
        is_arm = "arm" in machine or "aarch64" in machine

        if is_win:
            arch = "aarch64" if is_arm else "x86_64"
            url = f"https://github.com/tealdeer-rs/tealdeer/releases/download/v1.9.0/tealdeer-windows-{arch}-msvc.exe"
        elif sys.platform == "darwin":
            arch = "aarch64" if is_arm else "x86_64"
            url = f"https://github.com/tealdeer-rs/tealdeer/releases/download/v1.9.0/tealdeer-macos-{arch}"
        elif sys.platform.startswith("linux"):
            arch = "aarch64" if is_arm else "x86_64"
            url = f"https://github.com/tealdeer-rs/tealdeer/releases/download/v1.9.0/tealdeer-linux-{arch}-musl"
        else:
            url = None

        if url:
            urllib.request.urlretrieve(url, local_tldr)
            if not is_win:
                local_tldr.chmod(0o755)
            if local_tldr.exists():
                console.print(f"[bold #10b981]✔ Standalone binary installed to {local_tldr}[/]")
                _init_cache(console, local_tldr)
                return True
    except Exception as e:
        console.print(f"[yellow]  Standalone download fallback failed:[/] {e}")

    return bool(shutil.which("tldr") or shutil.which("tealdeer") or local_tldr.exists())


def _init_cache(console: Console, tldr_bin_path: Optional[Path] = None) -> None:
    """Initializes local tldr page cache via 'tldr --update'."""
    cmd = str(tldr_bin_path) if tldr_bin_path else (shutil.which("tldr") or shutil.which("tealdeer"))
    if cmd:
        try:
            subprocess.run([cmd, "--update"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=45)
            console.print("[dim]✔ Initialized tldr cheat sheet cache.[/]")
        except Exception:
            pass
