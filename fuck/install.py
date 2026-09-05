"""
Installer for thefuck plugin.
Installs thefuck using standard package managers (Homebrew on macOS/Linux, pipx on Windows/Linux).
If required package manager (pipx) is missing, installs pipx first before installing thefuck.
No virtual environments or ad-hoc hacks.
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
    Installs thefuck CLI tool across platforms:
    1. Check if thefuck is already available
    2. Try kps install / system package managers (e.g. Homebrew on macOS/Linux)
    3. If relying on pipx, install pipx first if missing, then install thefuck via pipx
    """
    if shutil.which("thefuck"):
        console.print("[dim]✔ thefuck is already available in PATH.[/]")
        return True

    is_win = sys.platform == "win32"
    system_name = platform.system().lower()
    console.print(f"[bold #00f0ff]📦 Installing thefuck for platform: {system_name}...[/]")

    # 1. Try unified package manager (kps install)
    if shutil.which("kps"):
        try:
            res = subprocess.run(["kps", "install", "thefuck"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
            if res.returncode == 0 and shutil.which("thefuck"):
                console.print("[bold #10b981]✔ thefuck successfully installed via kps install![/]")
                return True
        except Exception:
            pass

    # 2. Platform-specific: macOS / Linux (Homebrew)
    if (sys.platform == "darwin" or sys.platform.startswith("linux")) and shutil.which("brew"):
        try:
            console.print("[dim]  Attempting installation via Homebrew...[/]")
            res = subprocess.run(["brew", "install", "thefuck"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=180)
            if res.returncode == 0 and shutil.which("thefuck"):
                console.print("[bold #10b981]✔ thefuck installed via Homebrew![/]")
                return True
        except Exception:
            pass

    # 3. Dedicated package manager approach: pipx
    # If pipx is missing, install pipx first, then install thefuck via pipx
    pipx_cmd = shutil.which("pipx") or shutil.which("pipx.exe")
    if not pipx_cmd:
        console.print("[dim]  Required package manager 'pipx' is missing. Installing pipx first...[/]")
        try:
            if shutil.which("brew"):
                subprocess.run(["brew", "install", "pipx"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
            elif is_win and shutil.which("scoop"):
                subprocess.run(["scoop", "install", "pipx"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=90)
            elif is_win and shutil.which("winget"):
                subprocess.run(["winget", "install", "pipx", "--silent"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
            else:
                subprocess.run([sys.executable, "-m", "pip", "install", "pipx", "--quiet"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=90)
        except Exception as e:
            console.print(f"[yellow]  Warning during pipx installation:[/] {e}")

        pipx_cmd = shutil.which("pipx") or shutil.which("pipx.exe")

    if pipx_cmd:
        console.print("[dim]  Installing thefuck via pipx...[/]")
        try:
            res = subprocess.run([pipx_cmd, "install", "thefuck"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=180)
            if res.returncode == 0:
                # Run ensurepath to guarantee PATH availability
                subprocess.run([pipx_cmd, "ensurepath"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
                if shutil.which("thefuck"):
                    console.print("[bold #10b981]✔ thefuck successfully installed via pipx![/]")
                    return True
        except Exception as e:
            console.print(f"[yellow]  Warning during pipx install thefuck:[/] {e}")

    # 4. Fallback: Python pip install
    try:
        console.print("[dim]  Attempting direct pip install fallback...[/]")
        res = subprocess.run([sys.executable, "-m", "pip", "install", "thefuck", "--quiet"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
        if res.returncode == 0 and shutil.which("thefuck"):
            console.print("[bold #10b981]✔ thefuck installed via pip![/]")
            return True
    except Exception:
        pass

    if shutil.which("thefuck"):
        return True

    console.print("[yellow]Notice: thefuck installation finished. If not yet in PATH, restart terminal or check pipx path.[/]")
    return False
