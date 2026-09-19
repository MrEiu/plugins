"""
Installer for Autopilot (PM2 process manager) plugin.
Installs PM2 globally across platforms via npm, pnpm, yarn, scoop, or brew.
All comments and descriptions are in English.
"""

from pathlib import Path
import os
import platform
import shutil
import subprocess
import sys
from rich.console import Console


def _resolve_pm2_binary() -> str | None:
    """Checks for existing pm2 executable across PATH and known platform locations."""
    # 1. Standard PATH
    bin_path = shutil.which("pm2")
    if bin_path:
        return bin_path

    is_win = sys.platform == "win32"
    if is_win:
        bin_path_cmd = shutil.which("pm2.cmd")
        if bin_path_cmd:
            return bin_path_cmd

        user_profile = Path(os.environ.get("USERPROFILE", Path.home()))
        appdata = Path(os.environ.get("APPDATA", user_profile / "AppData" / "Roaming"))
        localappdata = Path(os.environ.get("LOCALAPPDATA", user_profile / "AppData" / "Local"))

        candidates = [
            appdata / "npm" / "pm2.cmd",
            appdata / "npm" / "pm2",
            user_profile / "scoop" / "shims" / "pm2.cmd",
            user_profile / "scoop" / "apps" / "pm2" / "current" / "pm2.cmd",
            localappdata / "pnpm" / "pm2.cmd",
            localappdata / "Yarn" / "bin" / "pm2.cmd",
            user_profile / ".local" / "bin" / "pm2.cmd",
        ]
        for candidate in candidates:
            if candidate.exists():
                return str(candidate)
    else:
        candidates = [
            Path("/usr/local/bin/pm2"),
            Path("/opt/homebrew/bin/pm2"),
            Path.home() / ".nvm" / "versions" / "node",
            Path.home() / ".local" / "share" / "pnpm" / "pm2",
            Path.home() / ".npm-global" / "bin" / "pm2",
        ]
        for candidate in candidates:
            if candidate.exists() and candidate.is_file():
                return str(candidate)

    return None


def install(console: Console, bin_dir: Path) -> bool:
    """
    Installs PM2 process manager:
    1. Verify if pm2 is already available.
    2. Try installing via npm (npm install -g pm2).
    3. Try installing via pnpm / yarn.
    4. On Windows: fallback to Scoop (scoop install pm2).
    5. On macOS / Linux: fallback to Homebrew (brew install pm2).
    """
    existing = _resolve_pm2_binary()
    if existing:
        console.print(f"[dim]✔ PM2 is already available at: {existing}[/]")
        return True

    system_name = platform.system().lower()
    console.print(f"[bold #00f0ff]📦 Installing PM2 process supervisor for platform: {system_name}...[/]")

    # 1. Try unified package manager (kps install pm2) if kps is present
    if shutil.which("kps"):
        try:
            res = subprocess.run(["kps", "install", "pm2"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
            if res.returncode == 0 and _resolve_pm2_binary():
                console.print("[bold #10b981]✔ PM2 successfully installed via kps install![/]")
                return True
        except Exception:
            pass

    # 2. Try npm (most standard and recommended distribution for PM2)
    npm_bin = shutil.which("npm.cmd") if sys.platform == "win32" else shutil.which("npm")
    if not npm_bin:
        npm_bin = shutil.which("npm")

    if npm_bin:
        console.print("[dim]→ Running npm install -g pm2...[/]")
        try:
            res = subprocess.run([npm_bin, "install", "-g", "pm2"], capture_output=True, text=True, timeout=180)
            if res.returncode == 0 and _resolve_pm2_binary():
                console.print("[bold #10b981]✔ PM2 successfully installed globally via npm![/]")
                return True
        except Exception as e:
            console.print(f"[dim yellow]npm install encountered an issue: {e}[/]")

    # 3. Try pnpm
    pnpm_bin = shutil.which("pnpm.cmd") if sys.platform == "win32" else shutil.which("pnpm")
    if pnpm_bin:
        try:
            res = subprocess.run([pnpm_bin, "add", "-g", "pm2"], capture_output=True, text=True, timeout=180)
            if res.returncode == 0 and _resolve_pm2_binary():
                console.print("[bold #10b981]✔ PM2 successfully installed via pnpm![/]")
                return True
        except Exception:
            pass

    # 4. Windows: Scoop
    if sys.platform == "win32":
        scoop_bin = shutil.which("scoop.cmd") or shutil.which("scoop")
        if scoop_bin:
            try:
                res = subprocess.run([scoop_bin, "install", "pm2"], capture_output=True, text=True, timeout=180)
                if res.returncode == 0 and _resolve_pm2_binary():
                    console.print("[bold #10b981]✔ PM2 successfully installed via Scoop![/]")
                    return True
            except Exception:
                pass

    # 5. macOS / Linux: Homebrew
    brew_bin = shutil.which("brew")
    if brew_bin:
        try:
            res = subprocess.run([brew_bin, "install", "pm2"], capture_output=True, text=True, timeout=180)
            if res.returncode == 0 and _resolve_pm2_binary():
                console.print("[bold #10b981]✔ PM2 successfully installed via Homebrew![/]")
                return True
        except Exception:
            pass

    # Final check
    resolved = _resolve_pm2_binary()
    if resolved:
        console.print(f"[bold #10b981]✔ PM2 detected at: {resolved}[/]")
        return True

    console.print("\n[bold #f43f5e]✘ Automatic installation of PM2 could not be completed.[/]")
    console.print("[yellow]Please ensure Node.js is installed, then run:[/]")
    console.print("[bold #00f0ff]  npm install -g pm2[/]\n")
    return False
