"""
Installer for profile (chezmoi dotfiles manager) plugin.
Installs chezmoi across platforms via package managers or official scripts.
All comments and descriptions are in English.
"""

from pathlib import Path
import platform
import shutil
import subprocess
import sys
from rich.console import Console


def install(console: Console, bin_dir: Path) -> bool:
    """
    Installs chezmoi dotfiles manager CLI across platforms:
    1. Check if chezmoi already exists in PATH or bin_dir
    2. Try kps install chezmoi
    3. Windows: Scoop, Winget, or official PowerShell one-liner script
    4. macOS / Linux: Homebrew or official curl one-liner script
    """
    bin_dir.mkdir(parents=True, exist_ok=True)
    is_win = sys.platform == "win32"
    local_chezmoi = bin_dir / ("chezmoi.exe" if is_win else "chezmoi")

    if shutil.which("chezmoi") or local_chezmoi.exists():
        console.print("[dim]✔ chezmoi is already installed.[/]")
        return True

    system_name = platform.system().lower()
    console.print(f"[bold #00f0ff]📦 Installing chezmoi for platform: {system_name}...[/]")

    # 1. Try unified package manager (kps install)
    if shutil.which("kps"):
        try:
            res = subprocess.run(["kps", "install", "chezmoi"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
            if res.returncode == 0 and shutil.which("chezmoi"):
                console.print("[bold #10b981]✔ chezmoi successfully installed via kps install![/]")
                return True
        except Exception:
            pass

    # 2. Windows: Scoop / Winget / official ps1 script
    if is_win:
        if shutil.which("scoop"):
            try:
                console.print("[dim]  Attempting installation via Scoop...[/]")
                res = subprocess.run(["scoop", "install", "chezmoi"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=90)
                if res.returncode == 0 and shutil.which("chezmoi"):
                    console.print("[bold #10b981]✔ chezmoi installed via Scoop![/]")
                    return True
            except Exception:
                pass

        if shutil.which("winget"):
            try:
                console.print("[dim]  Attempting installation via WinGet...[/]")
                res = subprocess.run(
                    ["winget", "install", "--id", "twpayne.chezmoi", "-e", "--silent", "--accept-source-agreements", "--accept-package-agreements"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=120,
                )
                if res.returncode == 0 and shutil.which("chezmoi"):
                    console.print("[bold #10b981]✔ chezmoi installed via WinGet![/]")
                    return True
            except Exception:
                pass

        # Official PowerShell one-liner script
        try:
            console.print("[dim]  Running official chezmoi PowerShell installer...[/]")
            cmd = f'powershell -NoProfile -ExecutionPolicy Bypass -Command "iex \\"&{{$(irm \'https://get.chezmoi.io/ps1\')}}\\" -b \'{bin_dir}\'"'
            res = subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=90)
            if local_chezmoi.exists():
                console.print(f"[bold #10b981]✔ chezmoi installed to {local_chezmoi} via official ps1 installer![/]")
                return True
        except Exception as e:
            console.print(f"[yellow]  PowerShell script failed:[/] {e}")

    # 3. macOS / Linux: Homebrew or official curl script
    else:
        if shutil.which("brew"):
            try:
                console.print("[dim]  Attempting installation via Homebrew...[/]")
                res = subprocess.run(["brew", "install", "chezmoi"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
                if res.returncode == 0 and shutil.which("chezmoi"):
                    console.print("[bold #10b981]✔ chezmoi installed via Homebrew![/]")
                    return True
            except Exception:
                pass

        # Official curl script
        try:
            console.print("[dim]  Running official chezmoi sh installer...[/]")
            cmd = f'sh -c "$(curl -fsLS get.chezmoi.io)" -- -b "{bin_dir}"'
            res = subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=90)
            if local_chezmoi.exists():
                local_chezmoi.chmod(0o755)
                console.print(f"[bold #10b981]✔ chezmoi installed to {local_chezmoi} via official sh installer![/]")
                return True
        except Exception as e:
            console.print(f"[yellow]  sh installer failed:[/] {e}")

    return bool(shutil.which("chezmoi") or local_chezmoi.exists())
