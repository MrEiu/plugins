"""
Installer for rec (pet snippet manager) plugin.
Installs pet across platforms via package managers or standalone binaries.
All comments and descriptions are in English.
"""

from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from rich.console import Console


def install(console: Console, bin_dir: Path) -> bool:
    """
    Installs pet snippet manager CLI across platforms:
    1. Check if pet already exists in PATH or bin_dir
    2. Try kps install pet
    3. Try Homebrew (macOS/Linux) or Scoop/Winget (Windows)
    4. Fallback: Official tar.gz archive from GitHub Releases
    """
    bin_dir.mkdir(parents=True, exist_ok=True)
    is_win = sys.platform == "win32"
    local_pet = bin_dir / ("pet.exe" if is_win else "pet")

    if shutil.which("pet") or local_pet.exists():
        console.print("[dim]✔ pet is already installed.[/]")
        return True

    system_name = platform.system().lower()
    console.print(f"[bold #00f0ff]📦 Installing pet snippet manager for platform: {system_name}...[/]")

    # 1. Try unified package manager (kps install)
    if shutil.which("kps"):
        try:
            res = subprocess.run(["kps", "install", "pet"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
            if res.returncode == 0 and shutil.which("pet"):
                console.print("[bold #10b981]✔ pet successfully installed via kps install![/]")
                return True
        except Exception:
            pass

    # 2. Platform-specific: macOS / Linux (Homebrew)
    if (sys.platform == "darwin" or sys.platform.startswith("linux")) and shutil.which("brew"):
        try:
            console.print("[dim]  Attempting installation via Homebrew...[/]")
            res = subprocess.run(["brew", "install", "pet"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
            if res.returncode == 0 and shutil.which("pet"):
                console.print("[bold #10b981]✔ pet installed via Homebrew![/]")
                return True
        except Exception:
            pass

    # 3. Platform-specific: Windows (Scoop / Winget)
    if is_win:
        if shutil.which("scoop"):
            try:
                console.print("[dim]  Attempting installation via Scoop...[/]")
                res = subprocess.run(["scoop", "install", "pet"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=90)
                if res.returncode == 0 and shutil.which("pet"):
                    console.print("[bold #10b981]✔ pet installed via Scoop![/]")
                    return True
            except Exception:
                pass

        if shutil.which("winget"):
            try:
                console.print("[dim]  Attempting installation via WinGet...[/]")
                res = subprocess.run(["winget", "install", "--id", "knqyf263.pet", "-e", "--silent"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=90)
                if res.returncode == 0 and shutil.which("pet"):
                    console.print("[bold #10b981]✔ pet installed via WinGet![/]")
                    return True
            except Exception:
                pass

    # 4. Fallback: Direct official standalone tar.gz release from GitHub
    try:
        console.print("[dim]  Downloading standalone pet binary from GitHub Releases...[/]")
        machine = platform.machine().lower()
        is_arm = "arm" in machine or "aarch64" in machine

        if is_win:
            arch = "arm64" if is_arm else "amd64"
            url = f"https://github.com/knqyf263/pet/releases/download/v1.0.1/pet_1.0.1_windows_{arch}.tar.gz"
        elif sys.platform == "darwin":
            arch = "arm64" if is_arm else "amd64"
            url = f"https://github.com/knqyf263/pet/releases/download/v1.0.1/pet_1.0.1_darwin_{arch}.tar.gz"
        elif sys.platform.startswith("linux"):
            arch = "arm64" if is_arm else "amd64"
            url = f"https://github.com/knqyf263/pet/releases/download/v1.0.1/pet_1.0.1_linux_{arch}.tar.gz"
        else:
            url = None

        if url:
            archive_path = bin_dir / "pet.tar.gz"
            urllib.request.urlretrieve(url, archive_path)
            with tarfile.open(archive_path, "r:gz") as tar:
                tar.extractall(path=bin_dir)
            archive_path.unlink(missing_ok=True)

            if not is_win and local_pet.exists():
                local_pet.chmod(0o755)

            if local_pet.exists():
                console.print(f"[bold #10b981]✔ Standalone binary installed to {local_pet}[/]")
                return True
    except Exception as e:
        console.print(f"[yellow]  Standalone download fallback failed:[/] {e}")

    return bool(shutil.which("pet") or local_pet.exists())
