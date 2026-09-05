"""
Installer for ai (aichat CLI) plugin.
Installs aichat across platforms via package managers or official standalone binaries.
All comments and descriptions are in English.
"""

from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import zipfile
from rich.console import Console


def install(console: Console, bin_dir: Path) -> bool:
    """
    Installs aichat CLI across platforms:
    1. Check if aichat already exists in PATH or bin_dir
    2. Try kps install aichat
    3. Try native package managers (Scoop, Winget, Homebrew, Cargo)
    4. Fallback: Official standalone release download from GitHub Releases
    """
    bin_dir.mkdir(parents=True, exist_ok=True)
    is_win = sys.platform == "win32"
    local_aichat = bin_dir / ("aichat.exe" if is_win else "aichat")

    if shutil.which("aichat") or local_aichat.exists():
        console.print("[dim]✔ aichat is already installed.[/]")
        return True

    system_name = platform.system().lower()
    console.print(f"[bold #00f0ff]📦 Installing aichat for platform: {system_name}...[/]")

    # 1. Try unified package manager (kps install)
    if shutil.which("kps"):
        try:
            res = subprocess.run(["kps", "install", "aichat"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
            if res.returncode == 0 and shutil.which("aichat"):
                console.print("[bold #10b981]✔ aichat successfully installed via kps install![/]")
                return True
        except Exception:
            pass

    # 2. Platform-specific: macOS / Linux (Homebrew)
    if (sys.platform == "darwin" or sys.platform.startswith("linux")) and shutil.which("brew"):
        try:
            console.print("[dim]  Attempting installation via Homebrew...[/]")
            res = subprocess.run(["brew", "install", "aichat"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
            if res.returncode == 0 and shutil.which("aichat"):
                console.print("[bold #10b981]✔ aichat installed via Homebrew![/]")
                return True
        except Exception:
            pass

    # 3. Platform-specific: Windows (Scoop / Winget)
    if is_win:
        if shutil.which("scoop"):
            try:
                console.print("[dim]  Attempting installation via Scoop...[/]")
                res = subprocess.run(["scoop", "install", "aichat"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=90)
                if res.returncode == 0 and shutil.which("aichat"):
                    console.print("[bold #10b981]✔ aichat installed via Scoop![/]")
                    return True
            except Exception:
                pass

        if shutil.which("winget"):
            try:
                console.print("[dim]  Attempting installation via WinGet...[/]")
                res = subprocess.run(
                    ["winget", "install", "--id", "sigoden.aichat", "-e", "--silent", "--accept-source-agreements", "--accept-package-agreements"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=90,
                )
                if res.returncode == 0 and shutil.which("aichat"):
                    console.print("[bold #10b981]✔ aichat installed via WinGet![/]")
                    return True
            except Exception:
                pass

    # 4. Cargo if available
    if shutil.which("cargo"):
        try:
            console.print("[dim]  Attempting installation via Cargo...[/]")
            res = subprocess.run(["cargo", "install", "--locked", "aichat"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=180)
            if res.returncode == 0 and shutil.which("aichat"):
                console.print("[bold #10b981]✔ aichat installed via Cargo![/]")
                return True
        except Exception:
            pass

    # 5. Fallback: Standalone prebuilt archive from GitHub Releases
    try:
        console.print("[dim]  Downloading standalone prebuilt binary from GitHub Releases...[/]")
        machine = platform.machine().lower()
        is_arm = "arm" in machine or "aarch64" in machine

        if is_win:
            arch = "aarch64" if is_arm else "x86_64"
            url = f"https://github.com/sigoden/aichat/releases/download/v0.30.0/aichat-v0.30.0-{arch}-pc-windows-msvc.zip"
            zip_path = bin_dir / "aichat.zip"
            urllib.request.urlretrieve(url, zip_path)
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(bin_dir)
            zip_path.unlink(missing_ok=True)
            if local_aichat.exists():
                console.print(f"[bold #10b981]✔ Standalone binary installed to {local_aichat}[/]")
                return True
        elif sys.platform == "darwin":
            arch = "aarch64" if is_arm else "x86_64"
            url = f"https://github.com/sigoden/aichat/releases/download/v0.30.0/aichat-v0.30.0-{arch}-apple-darwin.tar.gz"
            tar_path = bin_dir / "aichat.tar.gz"
            urllib.request.urlretrieve(url, tar_path)
            with tarfile.open(tar_path, "r:gz") as tf:
                tf.extractall(bin_dir)
            tar_path.unlink(missing_ok=True)
            if local_aichat.exists():
                local_aichat.chmod(0o755)
                console.print(f"[bold #10b981]✔ Standalone binary installed to {local_aichat}[/]")
                return True
        elif sys.platform.startswith("linux"):
            arch = "aarch64" if is_arm else "x86_64"
            url = f"https://github.com/sigoden/aichat/releases/download/v0.30.0/aichat-v0.30.0-{arch}-unknown-linux-musl.tar.gz"
            tar_path = bin_dir / "aichat.tar.gz"
            urllib.request.urlretrieve(url, tar_path)
            with tarfile.open(tar_path, "r:gz") as tf:
                tf.extractall(bin_dir)
            tar_path.unlink(missing_ok=True)
            if local_aichat.exists():
                local_aichat.chmod(0o755)
                console.print(f"[bold #10b981]✔ Standalone binary installed to {local_aichat}[/]")
                return True
    except Exception as e:
        console.print(f"[yellow]  Standalone download fallback failed:[/] {e}")

    return bool(shutil.which("aichat") or local_aichat.exists())
