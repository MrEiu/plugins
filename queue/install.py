"""
Installer for autopilot (Pueue task queue) plugin.
Installs pueue and pueued across platforms via package managers or cargo.
All comments and descriptions are in English.
"""

from pathlib import Path
import os
import platform
import shutil
import subprocess
import sys
from rich.console import Console


def install(console: Console, bin_dir: Path) -> bool:
    """
    Installs pueue & pueued CLI tools across platforms:
    1. Check existing PATH, Scoop, Kapsel bin, Cargo bin, WinGet
    2. Try kps install pueue
    3. Windows: Scoop or Winget
    4. macOS / Linux: Homebrew (brew install pueue)
    5. Cargo if available (cargo install --locked pueue)
    """
    is_win = sys.platform == "win32"

    if shutil.which("pueue"):
        console.print("[dim]✔ pueue is already available in PATH.[/]")
        return True

    # Check common known locations on Windows
    if is_win:
        user_profile = Path(os.environ.get("USERPROFILE", Path.home()))
        for candidate in [
            user_profile / "scoop/shims/pueue.exe",
            user_profile / "scoop/apps/pueue/current/pueue.exe",
            user_profile / ".cargo/bin/pueue.exe",
            user_profile / "AppData/Local/Microsoft/WinGet/Links/pueue.exe",
        ]:
            if candidate.exists():
                console.print(f"[dim]✔ pueue found at {candidate}[/]")
                return True

    system_name = platform.system().lower()
    console.print(f"[bold #00f0ff]📦 Installing pueue for platform: {system_name}...[/]")

    # 1. Try unified package manager (kps install)
    if shutil.which("kps"):
        try:
            res = subprocess.run(["kps", "install", "pueue"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
            if res.returncode == 0 and shutil.which("pueue"):
                console.print("[bold #10b981]✔ pueue successfully installed via kps install![/]")
                return True
        except Exception:
            pass

    # 2. Windows: Scoop / Winget
    if is_win:
        if shutil.which("scoop"):
            try:
                console.print("[dim]  Attempting installation via Scoop...[/]")
                res = subprocess.run(["scoop", "install", "pueue"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=90)
                if res.returncode == 0 and shutil.which("pueue"):
                    console.print("[bold #10b981]✔ pueue installed via Scoop![/]")
                    return True
            except Exception:
                pass

        if shutil.which("winget"):
            try:
                console.print("[dim]  Attempting installation via WinGet...[/]")
                res = subprocess.run(
                    ["winget", "install", "-e", "--id", "arnstn.pueue", "--accept-source-agreements", "--accept-package-agreements"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=90,
                )
                if res.returncode == 0 and shutil.which("pueue"):
                    console.print("[bold #10b981]✔ pueue installed via WinGet![/]")
                    return True
            except Exception:
                pass

    # 3. macOS / Linux: Homebrew
    if (sys.platform == "darwin" or sys.platform.startswith("linux")) and shutil.which("brew"):
        try:
            console.print("[dim]  Attempting installation via Homebrew...[/]")
            res = subprocess.run(["brew", "install", "pueue"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
            if res.returncode == 0 and shutil.which("pueue"):
                console.print("[bold #10b981]✔ pueue installed via Homebrew![/]")
                return True
        except Exception:
            pass

    if (bin_dir / f"pueue{'.exe' if is_win else ''}").exists():
        console.print(f"[dim]✔ pueue found in local bin directory: {bin_dir}[/]")
        return True

    # 4. Cargo fallback
    if shutil.which("cargo"):
        try:
            console.print("[dim]  Attempting installation via Cargo...[/]")
            res = subprocess.run(["cargo", "install", "--locked", "pueue"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=180)
            if res.returncode == 0 and shutil.which("pueue"):
                console.print("[bold #10b981]✔ pueue installed via Cargo![/]")
                return True
        except Exception:
            pass

    # 5. Direct GitHub Releases fallback (zero-dependency standalone download)
    if _download_github_release(console, bin_dir):
        return True

    return bool(shutil.which("pueue")) or (bin_dir / f"pueue{'.exe' if is_win else ''}").exists()


def _download_github_release(console: Console, bin_dir: Path) -> bool:
    """
    Downloads standalone precompiled pueue and pueued binaries directly from GitHub releases.
    Fallback when local package managers are unavailable.
    """
    import urllib.request

    is_win = sys.platform == "win32"
    is_mac = sys.platform == "darwin"
    is_linux = sys.platform.startswith("linux")
    machine = platform.machine().lower()

    base_url = "https://github.com/Nukesor/pueue/releases/latest/download"

    if is_win:
        pueue_asset = "pueue-x86_64-pc-windows-msvc.exe"
        pueued_asset = "pueued-x86_64-pc-windows-msvc.exe"
        pueue_target = bin_dir / "pueue.exe"
        pueued_target = bin_dir / "pueued.exe"
    elif is_mac:
        arch = "aarch64" if ("arm" in machine or "aarch64" in machine) else "x86_64"
        pueue_asset = f"pueue-{arch}-apple-darwin"
        pueued_asset = f"pueued-{arch}-apple-darwin"
        pueue_target = bin_dir / "pueue"
        pueued_target = bin_dir / "pueued"
    elif is_linux:
        arch = "aarch64" if ("arm" in machine or "aarch64" in machine) else "x86_64"
        pueue_asset = f"pueue-{arch}-unknown-linux-musl"
        pueued_asset = f"pueued-{arch}-unknown-linux-musl"
        pueue_target = bin_dir / "pueue"
        pueued_target = bin_dir / "pueued"
    else:
        return False

    console.print(f"[dim]  Attempting direct GitHub release download to {bin_dir}...[/]")
    try:
        bin_dir.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(f"{base_url}/{pueue_asset}", str(pueue_target))
        urllib.request.urlretrieve(f"{base_url}/{pueued_asset}", str(pueued_target))

        if not is_win:
            os.chmod(str(pueue_target), 0o755)
            os.chmod(str(pueued_target), 0o755)

        if pueue_target.exists() and pueued_target.exists():
            console.print("[bold #10b981]✔ pueue & pueued downloaded successfully from GitHub Releases![/]")
            return True
    except Exception as e:
        console.print(f"[dim]  Direct download fallback encountered error: {e}[/]")

    return False
