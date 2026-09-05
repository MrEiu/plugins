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

    return bool(shutil.which("pueue"))
