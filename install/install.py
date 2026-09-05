"""
Installer for install (meta-package-manager / mpm) plugin.
Installs mpm across platforms via package managers, pip, or standalone binaries.
All comments and descriptions are in English.
"""

from pathlib import Path
import platform
import shutil
import subprocess
import sys
import urllib.request
from rich.console import Console


def install(console: Console, bin_dir: Path) -> bool:
    """
    Installs meta-package-manager (mpm) CLI across platforms:
    1. Check if mpm already exists in PATH or bin_dir
    2. Try Scoop (Windows) or Homebrew (macOS/Linux)
    3. Try python pip install meta-package-manager
    4. Fallback: Official standalone binary from GitHub Releases
    """
    bin_dir.mkdir(parents=True, exist_ok=True)
    is_win = sys.platform == "win32"
    local_mpm = bin_dir / ("mpm.exe" if is_win else "mpm")

    if shutil.which("mpm") or local_mpm.exists():
        console.print("[dim]✔ meta-package-manager (mpm) is already installed.[/]")
        return True

    system_name = platform.system().lower()
    console.print(f"[bold #00f0ff]📦 Installing meta-package-manager for platform: {system_name}...[/]")

    # 1. Platform-specific package managers
    if is_win and shutil.which("scoop"):
        try:
            console.print("[dim]  Attempting installation via Scoop...[/]")
            res = subprocess.run(["scoop", "install", "main/meta-package-manager"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=90)
            if res.returncode == 0 and shutil.which("mpm"):
                console.print("[bold #10b981]✔ mpm installed via Scoop![/]")
                return True
        except Exception:
            pass
    elif (sys.platform == "darwin" or sys.platform.startswith("linux")) and shutil.which("brew"):
        try:
            console.print("[dim]  Attempting installation via Homebrew...[/]")
            res = subprocess.run(["brew", "install", "meta-package-manager"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=90)
            if res.returncode == 0 and shutil.which("mpm"):
                console.print("[bold #10b981]✔ mpm installed via Homebrew![/]")
                return True
        except Exception:
            pass

    # 2. Python pip
    try:
        console.print("[dim]  Attempting installation via pip...[/]")
        res = subprocess.run([sys.executable, "-m", "pip", "install", "meta-package-manager", "--quiet"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
        if res.returncode == 0 and shutil.which("mpm"):
            console.print("[bold #10b981]✔ mpm installed via pip![/]")
            return True
    except Exception:
        pass

    # 3. Fallback: Direct official standalone binary from GitHub Releases
    try:
        console.print("[dim]  Downloading standalone mpm binary from GitHub Releases...[/]")
        machine = platform.machine().lower()
        is_arm = "arm" in machine or "aarch64" in machine

        if is_win:
            url = "https://github.com/kdeldycke/meta-package-manager/releases/latest/download/meta-package-manager-windows-x64.exe"
        elif sys.platform == "darwin":
            url = f"https://github.com/kdeldycke/meta-package-manager/releases/latest/download/meta-package-manager-macos-{'arm64' if is_arm else 'x64'}.bin"
        elif sys.platform.startswith("linux"):
            url = f"https://github.com/kdeldycke/meta-package-manager/releases/latest/download/meta-package-manager-linux-{'arm64' if is_arm else 'x64'}.bin"
        else:
            url = None

        if url:
            urllib.request.urlretrieve(url, local_mpm)
            if not is_win:
                local_mpm.chmod(0o755)
            if local_mpm.exists():
                console.print(f"[bold #10b981]✔ Standalone binary installed to {local_mpm}[/]")
                return True
    except Exception as e:
        console.print(f"[yellow]  Standalone download fallback failed:[/] {e}")

    return bool(shutil.which("mpm") or local_mpm.exists())
