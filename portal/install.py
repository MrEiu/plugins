"""
Installer for portal (directory navigation) plugin.
Installs both zoxide (core frecency database) and fd (fast filesystem directory finder)
across platforms via package managers (Scoop, WinGet, Homebrew, Cargo)
or standalone prebuilt binaries from GitHub Releases.
All comments and descriptions are in English.
"""

from pathlib import Path
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import zipfile

from rich.console import Console


def _install_zoxide(console: Console, bin_dir: Path) -> bool:
    """Installs zoxide CLI across platforms."""
    is_win = sys.platform == "win32"
    local_zoxide = bin_dir / ("zoxide.exe" if is_win else "zoxide")

    if shutil.which("zoxide") or local_zoxide.exists():
        console.print("[dim]✔ zoxide is already installed and available.[/]")
        return True

    if is_win:
        user_home = Path(os.environ.get("USERPROFILE", Path.home()))
        for candidate in [
            user_home / "scoop/shims/zoxide.exe",
            user_home / "scoop/apps/zoxide/current/zoxide.exe",
            user_home / "AppData/Local/Microsoft/WinGet/Links/zoxide.exe",
            user_home / ".cargo/bin/zoxide.exe",
        ]:
            if candidate.exists():
                console.print(f"[dim]✔ zoxide found at {candidate}[/]")
                return True

    system_name = platform.system().lower()
    console.print(f"[bold #00f0ff]📦 Installing zoxide for platform: {system_name}...[/]")

    # 1. Windows: Scoop / Winget
    if is_win:
        if shutil.which("scoop"):
            try:
                console.print("[dim]  Attempting zoxide installation via Scoop...[/]")
                res = subprocess.run(["scoop", "install", "zoxide"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
                if res.returncode == 0 and (shutil.which("zoxide") or (user_home / "scoop/shims/zoxide.exe").exists()):
                    console.print("[bold #10b981]✔ zoxide installed via Scoop![/]")
                    return True
            except Exception:
                pass

        if shutil.which("winget"):
            try:
                console.print("[dim]  Attempting zoxide installation via WinGet...[/]")
                res = subprocess.run(
                    ["winget", "install", "--id", "ajeetdsouza.zoxide", "-e", "--silent", "--accept-source-agreements", "--accept-package-agreements"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=120,
                )
                if res.returncode == 0 and shutil.which("zoxide"):
                    console.print("[bold #10b981]✔ zoxide installed via WinGet![/]")
                    return True
            except Exception:
                pass

    # 2. macOS / Linux: Homebrew
    if (sys.platform == "darwin" or sys.platform.startswith("linux")) and shutil.which("brew"):
        try:
            console.print("[dim]  Attempting zoxide installation via Homebrew...[/]")
            res = subprocess.run(["brew", "install", "zoxide"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
            if res.returncode == 0 and shutil.which("zoxide"):
                console.print("[bold #10b981]✔ zoxide installed via Homebrew![/]")
                return True
        except Exception:
            pass

    # 3. Cargo fallback
    if shutil.which("cargo"):
        try:
            console.print("[dim]  Attempting zoxide installation via Cargo...[/]")
            res = subprocess.run(["cargo", "install", "zoxide", "--locked"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=240)
            if res.returncode == 0 and shutil.which("zoxide"):
                console.print("[bold #10b981]✔ zoxide installed via Cargo![/]")
                return True
        except Exception:
            pass

    # 4. Fallback: Direct standalone binary download from GitHub Releases
    try:
        console.print("[dim]  Downloading standalone prebuilt zoxide binary from GitHub Releases...[/]")
        machine = platform.machine().lower()
        version = "0.10.0"

        if is_win:
            arch = "x86_64-pc-windows-msvc" if "64" in machine or "amd64" in machine else "i686-pc-windows-msvc"
            asset_name = f"zoxide-{version}-{arch}.zip"
            download_url = f"https://github.com/ajeetdsouza/zoxide/releases/download/v{version}/{asset_name}"
            archive_path = bin_dir / asset_name

            urllib.request.urlretrieve(download_url, archive_path)
            with zipfile.ZipFile(archive_path, "r") as zip_ref:
                for member in zip_ref.namelist():
                    if member.endswith("zoxide.exe"):
                        with zip_ref.open(member) as source, open(local_zoxide, "wb") as target:
                            shutil.copyfileobj(source, target)
                        break
            archive_path.unlink(missing_ok=True)

        elif sys.platform == "darwin":
            arch = "aarch64-apple-darwin" if "arm" in machine or "aarch64" in machine else "x86_64-apple-darwin"
            asset_name = f"zoxide-{version}-{arch}.tar.gz"
            download_url = f"https://github.com/ajeetdsouza/zoxide/releases/download/v{version}/{asset_name}"
            archive_path = bin_dir / asset_name

            urllib.request.urlretrieve(download_url, archive_path)
            with tarfile.open(archive_path, "r:gz") as tar:
                for member in tar.getmembers():
                    if member.name.endswith("zoxide"):
                        f = tar.extractfile(member)
                        if f:
                            with open(local_zoxide, "wb") as target:
                                shutil.copyfileobj(f, target)
                        break
            archive_path.unlink(missing_ok=True)
            local_zoxide.chmod(0o755)

        else:
            arch = "x86_64-unknown-linux-musl" if "64" in machine or "amd64" in machine else "i686-unknown-linux-musl"
            asset_name = f"zoxide-{version}-{arch}.tar.gz"
            download_url = f"https://github.com/ajeetdsouza/zoxide/releases/download/v{version}/{asset_name}"
            archive_path = bin_dir / asset_name

            urllib.request.urlretrieve(download_url, archive_path)
            with tarfile.open(archive_path, "r:gz") as tar:
                for member in tar.getmembers():
                    if member.name.endswith("zoxide"):
                        f = tar.extractfile(member)
                        if f:
                            with open(local_zoxide, "wb") as target:
                                shutil.copyfileobj(f, target)
                        break
            archive_path.unlink(missing_ok=True)
            local_zoxide.chmod(0o755)

        if local_zoxide.exists():
            console.print(f"[bold #10b981]✔ zoxide successfully downloaded to: [white]{local_zoxide}[/][/]")
            return True

    except Exception as e:
        console.print(f"[bold #f43f5e]Failed to download standalone zoxide:[/] {e}")

    return False


def _install_fd(console: Console, bin_dir: Path) -> bool:
    """Installs fd (fast directory search tool) across platforms."""
    is_win = sys.platform == "win32"
    local_fd = bin_dir / ("fd.exe" if is_win else "fd")

    # Check PATH (either fd or Debian/Ubuntu fdfind)
    if shutil.which("fd") or shutil.which("fdfind") or local_fd.exists():
        console.print("[dim]✔ fd is already installed and available.[/]")
        return True

    if is_win:
        user_home = Path(os.environ.get("USERPROFILE", Path.home()))
        for candidate in [
            user_home / "scoop/shims/fd.exe",
            user_home / "scoop/apps/fd/current/fd.exe",
            user_home / "AppData/Local/Microsoft/WinGet/Links/fd.exe",
            user_home / ".cargo/bin/fd.exe",
        ]:
            if candidate.exists():
                console.print(f"[dim]✔ fd found at {candidate}[/]")
                return True

    system_name = platform.system().lower()
    console.print(f"[bold #00f0ff]📦 Installing fd (search engine) for platform: {system_name}...[/]")

    # 1. Windows: Scoop / Winget
    if is_win:
        if shutil.which("scoop"):
            try:
                console.print("[dim]  Attempting fd installation via Scoop...[/]")
                res = subprocess.run(["scoop", "install", "fd"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
                if res.returncode == 0 and (shutil.which("fd") or (user_home / "scoop/shims/fd.exe").exists()):
                    console.print("[bold #10b981]✔ fd installed via Scoop![/]")
                    return True
            except Exception:
                pass

        if shutil.which("winget"):
            try:
                console.print("[dim]  Attempting fd installation via WinGet...[/]")
                res = subprocess.run(
                    ["winget", "install", "--id", "sharkdp.fd", "-e", "--silent", "--accept-source-agreements", "--accept-package-agreements"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=120,
                )
                if res.returncode == 0 and shutil.which("fd"):
                    console.print("[bold #10b981]✔ fd installed via WinGet![/]")
                    return True
            except Exception:
                pass

    # 2. macOS / Linux: Homebrew
    if (sys.platform == "darwin" or sys.platform.startswith("linux")) and shutil.which("brew"):
        try:
            console.print("[dim]  Attempting fd installation via Homebrew...[/]")
            res = subprocess.run(["brew", "install", "fd"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
            if res.returncode == 0 and (shutil.which("fd") or shutil.which("fdfind")):
                console.print("[bold #10b981]✔ fd installed via Homebrew![/]")
                return True
        except Exception:
            pass

    # 3. Cargo fallback
    if shutil.which("cargo"):
        try:
            console.print("[dim]  Attempting fd installation via Cargo...[/]")
            res = subprocess.run(["cargo", "install", "fd-find", "--locked"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=240)
            if res.returncode == 0 and shutil.which("fd"):
                console.print("[bold #10b981]✔ fd installed via Cargo![/]")
                return True
        except Exception:
            pass

    # 4. Fallback: Direct standalone binary download from GitHub Releases
    try:
        console.print("[dim]  Downloading standalone prebuilt fd binary from GitHub Releases...[/]")
        machine = platform.machine().lower()
        version = "10.2.0"

        if is_win:
            arch = "x86_64-pc-windows-msvc" if "64" in machine or "amd64" in machine else "i686-pc-windows-msvc"
            asset_name = f"fd-v{version}-{arch}.zip"
            download_url = f"https://github.com/sharkdp/fd/releases/download/v{version}/{asset_name}"
            archive_path = bin_dir / asset_name

            urllib.request.urlretrieve(download_url, archive_path)
            with zipfile.ZipFile(archive_path, "r") as zip_ref:
                for member in zip_ref.namelist():
                    if member.endswith("fd.exe"):
                        with zip_ref.open(member) as source, open(local_fd, "wb") as target:
                            shutil.copyfileobj(source, target)
                        break
            archive_path.unlink(missing_ok=True)

        elif sys.platform == "darwin":
            arch = "aarch64-apple-darwin" if "arm" in machine or "aarch64" in machine else "x86_64-apple-darwin"
            asset_name = f"fd-v{version}-{arch}.tar.gz"
            download_url = f"https://github.com/sharkdp/fd/releases/download/v{version}/{asset_name}"
            archive_path = bin_dir / asset_name

            urllib.request.urlretrieve(download_url, archive_path)
            with tarfile.open(archive_path, "r:gz") as tar:
                for member in tar.getmembers():
                    if member.name.endswith("/fd") or member.name.endswith("fd"):
                        f = tar.extractfile(member)
                        if f:
                            with open(local_fd, "wb") as target:
                                shutil.copyfileobj(f, target)
                        break
            archive_path.unlink(missing_ok=True)
            local_fd.chmod(0o755)

        else:
            arch = "x86_64-unknown-linux-musl" if "64" in machine or "amd64" in machine else "i686-unknown-linux-musl"
            asset_name = f"fd-v{version}-{arch}.tar.gz"
            download_url = f"https://github.com/sharkdp/fd/releases/download/v{version}/{asset_name}"
            archive_path = bin_dir / asset_name

            urllib.request.urlretrieve(download_url, archive_path)
            with tarfile.open(archive_path, "r:gz") as tar:
                for member in tar.getmembers():
                    if member.name.endswith("/fd") or member.name.endswith("fd"):
                        f = tar.extractfile(member)
                        if f:
                            with open(local_fd, "wb") as target:
                                shutil.copyfileobj(f, target)
                        break
            archive_path.unlink(missing_ok=True)
            local_fd.chmod(0o755)

        if local_fd.exists():
            console.print(f"[bold #10b981]✔ fd successfully downloaded to: [white]{local_fd}[/][/]")
            return True

    except Exception as e:
        console.print(f"[dim]  Note: Supplementary fd download skipped or failed: {e}[/]")

    return False


def install(console: Console, bin_dir: Path) -> bool:
    """
    Installs portal navigation tools across platforms:
    1. Primary: zoxide (frecency database)
    2. Supplementary: fd (fast directory search engine)
    """
    bin_dir.mkdir(parents=True, exist_ok=True)

    zoxide_ok = _install_zoxide(console, bin_dir)
    _install_fd(console, bin_dir)

    return zoxide_ok
