"""
Kapsel kssh Plugin - Interactive SSH Session Bridge.
Wraps OpenSSH execution with:
- In-session 'Alt+S' hotkey interception for file upload & port forwarding
- Transparent signal passthrough (Ctrl+C sends SIGINT to remote process)
- Automatic host connection recording (capped at 4 recent hosts)
- Dynamic tunnel cleanup upon session termination
All comments and docstrings are in English.
"""

import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional
try:
    import select
except ImportError:
    select = None

from rich.console import Console

from .config import record_connection
from .transfer import (
    check_remote_file_exists,
    execute_scp_upload,
    probe_remote_pwd,
)
from .tunnel import tunnel_manager


def resolve_local_upload_path(raw_path: str) -> str:
    """
    Normalizes local path and converts Windows drive paths (e.g. C:\\...)
    to WSL paths (/mnt/c/...) when running in WSL/Linux.
    """
    clean = os.path.expanduser(raw_path.strip().strip("'\""))
    if not clean:
        return clean

    if sys.platform != "win32" and len(clean) >= 2 and clean[1] == ":":
        drive = clean[0].lower()
        rest = clean[2:].replace("\\", "/")
        return f"/mnt/{drive}{rest}"
    return clean


def ensure_secure_key_path(key_path: Optional[str]) -> Optional[str]:
    """
    Ensures private key file has secure permissions (0600) on POSIX/WSL.
    On WSL DrvFs mounts (/mnt/c/...), permissions often default to 0777 and
    chmod fails to restrict them. OpenSSH rejects private keys with 0777.
    This helper auto-copies the key to ~/.kapsel/secure_keys/ with mode 0600.
    """
    if not key_path or not os.path.isfile(key_path):
        return key_path

    if sys.platform == "win32":
        return key_path

    try:
        st = os.stat(key_path)
        if (st.st_mode & 0o077) != 0:
            try:
                os.chmod(key_path, 0o600)
                st = os.stat(key_path)
                if (st.st_mode & 0o077) == 0:
                    return key_path
            except Exception:
                pass

            kapsel_keys = Path.home() / ".kapsel" / "secure_keys"
            kapsel_keys.mkdir(parents=True, exist_ok=True)
            dest_key = kapsel_keys / Path(key_path).name
            shutil.copy2(key_path, dest_key)
            os.chmod(dest_key, 0o600)
            return str(dest_key)
    except Exception:
        pass

    return key_path


def _read_char_direct() -> bytes:
    """Reads a raw byte from console input on Windows or Unix/WSL."""
    if sys.platform == "win32":
        import msvcrt
        return msvcrt.getch()
    else:
        import termios
        import tty
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            return os.read(fd, 1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def handle_in_session_menu(
    host: str,
    user: str = "root",
    port: int = 22,
    key_path: Optional[str] = None,
    console: Optional[Console] = None,
) -> None:
    """
    Renders the non-intrusive bottom-bar menu when Alt+S is triggered.
    Prompts for:
    - 'u': File upload to remote current working directory (with duplicate collision check)
    - 'p': Port forwarding (remote->local default, 'r' for local->remote reverse tunnel)
    - 'Esc': Cancel and return to session
    """
    con = console or Console(legacy_windows=False)

    # Move to new line and print menu
    sys.stdout.write(
        "\r\n\x1b[7;36m [kssh] \x1b[0m \x1b[1;37mu: Upload file  p: Port forward  (Esc: Cancel) > \x1b[0m"
    )
    sys.stdout.flush()

    # Read action key
    choice_byte = _read_char_direct()
    choice_str = choice_byte.decode("utf-8", errors="ignore").lower()

    if choice_byte in (b"\x1b", b"\x03", b"q", b"Q") or choice_str not in ("u", "p"):
        sys.stdout.write("\r\x1b[K\x1b[dim][kssh] Cancelled. Returning to session.\x1b[0m\r\n")
        sys.stdout.flush()
        return

    # 1. File Upload Flow
    if choice_str == "u":
        sys.stdout.write("\r\x1b[K\x1b[1;36m[kssh 上传]\x1b[0m 请输入要上传的本地文件路径 (支持拖拽): ")
        sys.stdout.flush()
        try:
            raw_local = input().strip()
        except (KeyboardInterrupt, EOFError):
            sys.stdout.write("\r\x1b[K\x1b[dim][kssh] 上传已取消。\x1b[0m\r\n")
            sys.stdout.flush()
            return

        clean_local = resolve_local_upload_path(raw_local)
        if not clean_local or not os.path.exists(clean_local):
            sys.stdout.write(f"\r\x1b[K\x1b[1;31m[kssh 错误]\x1b[0m 本地文件不存在: {raw_local}\r\n")
            sys.stdout.flush()
            time.sleep(1.2)
            return

        filename = os.path.basename(clean_local)

        # Detect remote PWD
        sys.stdout.write("\r\x1b[K\x1b[dim][kssh] 正在检测远端当前工作目录...\x1b[0m")
        sys.stdout.flush()
        remote_pwd = probe_remote_pwd(host, user, port, key_path)

        sys.stdout.write(f"\r\x1b[K\x1b[1;36m[kssh 上传]\x1b[0m 目标远程目录 [回车确认默认: {remote_pwd}]: ")
        sys.stdout.flush()
        try:
            chosen_remote_dir = input().strip()
        except (KeyboardInterrupt, EOFError):
            sys.stdout.write("\r\x1b[K\x1b[dim][kssh] 上传已取消。\x1b[0m\r\n")
            sys.stdout.flush()
            return

        if not chosen_remote_dir:
            chosen_remote_dir = remote_pwd

        # Clean remote path formatting
        norm_dir = chosen_remote_dir.rstrip("/").replace("\\", "/")
        dest_filename = filename
        remote_dest = f"{norm_dir}/{dest_filename}"

        # Collision checking
        sys.stdout.write(f"\r\x1b[K\x1b[dim][kssh] 正在检查远端目标文件: {remote_dest}...\x1b[0m")
        sys.stdout.flush()

        if check_remote_file_exists(remote_dest, host, user, port, key_path):
            sys.stdout.write(
                f"\r\x1b[K\x1b[1;33m[kssh 提示]\x1b[0m 远端已存在同名文件: \x1b[white]{remote_dest}\x1b[0m\r\n"
                "\x1b[1;36m[o] 覆盖 (Overwrite)  [r] 重命名 (Rename)  [c] 取消 (Cancel): \x1b[0m"
            )
            sys.stdout.flush()

            col_choice = _read_char_direct().decode("utf-8", errors="ignore").lower()
            if col_choice == "o":
                sys.stdout.write("\r\x1b[K\x1b[dim]确认覆盖。\x1b[0m\r\n")
                sys.stdout.flush()
            elif col_choice == "r":
                sys.stdout.write("\r\x1b[K\x1b[1;36m请输入新文件名: \x1b[0m")
                sys.stdout.flush()
                try:
                    new_name = input().strip()
                except (KeyboardInterrupt, EOFError):
                    sys.stdout.write("\r\x1b[K\x1b[dim][kssh] 上传已取消。\x1b[0m\r\n")
                    sys.stdout.flush()
                    return
                if new_name:
                    dest_filename = new_name
                    remote_dest = f"{norm_dir}/{dest_filename}"
                else:
                    sys.stdout.write("\r\x1b[K\x1b[dim][kssh] 文件名为空，上传已取消。\x1b[0m\r\n")
                    sys.stdout.flush()
                    return
            else:
                sys.stdout.write("\r\x1b[K\x1b[dim][kssh] 上传已取消。\x1b[0m\r\n")
                sys.stdout.flush()
                return

        # Execute upload
        sys.stdout.write(f"\r\x1b[K\x1b[1;36m[kssh 上传中]\x1b[0m {filename} -> {remote_dest} ...\r\n")
        sys.stdout.flush()

        ok, msg = execute_scp_upload(clean_local, remote_dest, host, user, port, key_path)
        if ok:
            sys.stdout.write(f"\x1b[1;32m[kssh ✓]\x1b[0m 上传成功: {remote_dest}\r\n")
        else:
            sys.stdout.write(f"\x1b[1;31m[kssh 失败]\x1b[0m {msg}\r\n")
        sys.stdout.flush()
        time.sleep(1.0)
        return

    # 2. Port Forwarding Flow
    if choice_str == "p":
        sys.stdout.write(
            "\r\x1b[K\x1b[1;36m[kssh 端口转发]\x1b[0m 请输入端口 (如 \x1b[white]3306\x1b[0m 远端->本地，或 \x1b[white]r 8000\x1b[0m 本地->远端): "
        )
        sys.stdout.flush()
        try:
            port_input = input().strip()
        except (KeyboardInterrupt, EOFError):
            sys.stdout.write("\r\x1b[K\x1b[dim][kssh] 转发已取消。\x1b[0m\r\n")
            sys.stdout.flush()
            return

        if not port_input:
            sys.stdout.write("\r\x1b[K\x1b[dim][kssh] 端口为空，已取消。\x1b[0m\r\n")
            sys.stdout.flush()
            return

        ok, msg = tunnel_manager.start_tunnel(
            spec_str=port_input,
            host=host,
            user=user,
            ssh_port=port,
            key_path=key_path,
        )
        if ok:
            sys.stdout.write(f"\r\x1b[K\x1b[1;32m[kssh ✓]\x1b[0m {msg}\r\n")
        else:
            sys.stdout.write(f"\r\x1b[K\x1b[1;31m[kssh 失败]\x1b[0m {msg}\r\n")
        sys.stdout.flush()
        time.sleep(1.2)
        return


def run_ssh_session(
    host: str,
    user: str = "root",
    port: int = 22,
    name: Optional[str] = None,
    key_path: Optional[str] = None,
    extra_ssh_args: Optional[List[str]] = None,
    console: Optional[Console] = None,
) -> int:
    """
    Initiates an interactive SSH connection.
    Automatically records host history and handles in-session hotkey Alt+S.
    """
    con = console or Console(legacy_windows=False)
    ssh_bin = shutil.which("ssh") or "ssh"

    # Ensure secure key permissions on POSIX/WSL
    key_path = ensure_secure_key_path(key_path)

    # Check for WSL target routing (e.g. 'wsl' or 'wsl:Ubuntu') on Windows
    if sys.platform == "win32" and (host.lower() == "wsl" or host.lower().startswith("wsl:")):
        distro = host.split(":", 1)[1] if ":" in host else None
        wsl_bin = shutil.which("wsl.exe") or shutil.which("wsl") or "wsl.exe"
        cmd = [wsl_bin]
        if distro:
            cmd.extend(["-d", distro])
        if user and user not in ("root", "current"):
            cmd.extend(["-u", user])
        if extra_ssh_args:
            cmd.extend(extra_ssh_args)
        target_display = f"wsl:{distro or 'default'}"
    else:
        cmd = [
            ssh_bin,
            "-tt",
            "-p", str(port),
            "-o", "StrictHostKeyChecking=accept-new",
        ]
        if key_path and os.path.isfile(key_path):
            cmd.extend(["-i", key_path])
        if extra_ssh_args:
            cmd.extend(extra_ssh_args)
        cmd.append(f"{user}@{host}")
        target_display = f"{user}@{host}:{port}"

    con.print(f"\n[bold #00f0ff]🌐 Kssh Connecting:[/] [white]{target_display}[/] [dim]({name or host})[/]")
    con.print("[dim]In-session shortcuts: [bold white]Alt+S[/bold white] (Menu)[/dim]\n")

    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=None,  # Native terminal stdout passthrough
            stderr=None,
        )
    except Exception as e:
        con.print(f"[bold #f43f5e]Failed to start SSH:[/] {e}")
        return 1

    # Windows input loop
    if sys.platform == "win32":
        import msvcrt


        # Ignore Ctrl+C in parent process so SIGINT passes through via proc.stdin
        def _ignore_sigint(sig, frame):
            try:
                if proc.poll() is None and proc.stdin:
                    proc.stdin.write(b"\x03")
                    proc.stdin.flush()
            except Exception:
                pass

        old_sigint = signal.signal(signal.SIGINT, _ignore_sigint)

        try:
            while proc.poll() is None:
                if msvcrt.kbhit():
                    ch = msvcrt.getch()

                    # Check for Alt+S
                    # Case 1: scan code 31 (b'\x00' followed by b'\x1f')
                    if ch == b"\x00":
                        if msvcrt.kbhit():
                            ext = msvcrt.getch()
                            if ext == b"\x1f":  # Alt+S
                                handle_in_session_menu(host, user, port, key_path, con)
                                continue
                            else:
                                if proc.stdin:
                                    proc.stdin.write(ch + ext)
                                    proc.stdin.flush()
                                continue
                        else:
                            if proc.stdin:
                                proc.stdin.write(ch)
                                proc.stdin.flush()
                            continue

                    # Case 2: VT sequence for Alt+s (\x1bs or \x1bS)
                    if ch == b"\x1b":
                        time.sleep(0.02)
                        if msvcrt.kbhit():
                            next_ch = msvcrt.getch()
                            if next_ch in (b"s", b"S"):
                                handle_in_session_menu(host, user, port, key_path, con)
                                continue
                            else:
                                if proc.stdin:
                                    proc.stdin.write(ch + next_ch)
                                    proc.stdin.flush()
                                continue
                        else:
                            if proc.stdin:
                                proc.stdin.write(ch)
                                proc.stdin.flush()
                            continue

                    # Case 3: Ctrl+C (b'\x03') -> write directly to ssh stdin
                    if ch == b"\x03":
                        if proc.stdin:
                            proc.stdin.write(b"\x03")
                            proc.stdin.flush()
                        continue

                    # Case 4: Extended keys (arrows, Home, End, Del)
                    if ch == b"\xe0":
                        if msvcrt.kbhit():
                            ext = msvcrt.getch()
                            vt_map = {
                                b"H": b"\x1b[A",  # Up
                                b"P": b"\x1b[B",  # Down
                                b"M": b"\x1b[C",  # Right
                                b"K": b"\x1b[D",  # Left
                                b"G": b"\x1b[H",  # Home
                                b"O": b"\x1b[F",  # End
                                b"S": b"\x1b[3~", # Del
                                b"I": b"\x1b[5~", # PgUp
                                b"Q": b"\x1b[6~", # PgDn
                            }
                            data = vt_map.get(ext, ch + ext)
                            if proc.stdin:
                                proc.stdin.write(data)
                                proc.stdin.flush()
                            continue

                    # Standard character input
                    if proc.stdin:
                        try:
                            proc.stdin.write(ch)
                            proc.stdin.flush()
                        except (BrokenPipeError, OSError):
                            break
                else:
                    time.sleep(0.01)

        except Exception:
            pass
        finally:
            signal.signal(signal.SIGINT, old_sigint)

    else:
        # Unix / macOS / WSL input loop
        import termios
        import tty

        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            while proc.poll() is None:
                r, _, _ = select.select([fd], [], [], 0.02)
                if r:
                    ch = os.read(fd, 1)
                    if ch == b"\x1b":
                        # Check if followed by 's' (Alt+S)
                        r_sub, _, _ = select.select([fd], [], [], 0.03)
                        if r_sub:
                            next_ch = os.read(fd, 1)
                            if next_ch in (b"s", b"S"):
                                # Restore terminal temporarily for menu
                                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
                                handle_in_session_menu(host, user, port, key_path, con)
                                tty.setraw(fd)
                                continue
                            else:
                                if proc.stdin:
                                    proc.stdin.write(ch + next_ch)
                                    proc.stdin.flush()
                                continue
                    if proc.stdin:
                        proc.stdin.write(ch)
                        proc.stdin.flush()
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    ret = proc.wait()
    # Clean up all active tunnels spawned during the session
    tunnel_manager.stop_all()

    con.print(f"\n[dim][kssh] SSH session ended (exit code: {ret})[/dim]")
    return ret
