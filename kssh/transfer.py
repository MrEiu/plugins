"""
Kapsel kssh Plugin - File Transfer Engine.
Handles uploading files to remote current working directory (PWD) with collision detection.
Prompts for overwrite/rename/cancel when remote destination file already exists.
All comments and docstrings are in English.
"""

import os
from pathlib import Path
import shlex
import shutil
import subprocess
from typing import Optional, Tuple


def _resolve_ssh_bin() -> str:
    """Finds the system ssh executable."""
    return shutil.which("ssh") or "ssh"


def _resolve_scp_bin() -> str:
    """Finds the system scp executable."""
    return shutil.which("scp") or "scp"


def probe_remote_pwd(
    host: str,
    user: str = "root",
    port: int = 22,
    key_path: Optional[str] = None,
    timeout: int = 3,
) -> str:
    """
    Attempts to detect the current working directory of the user's active remote shell session.
    Inspects /proc/<pts_shell_pid>/cwd if accessible on Linux, falling back to 'pwd' (~).
    """
    ssh_bin = _resolve_ssh_bin()
    probe_script = (
        "pts_pid=$(ps -u $(id -u) -o pid,tty,comm 2>/dev/null | grep -E 'pts/[0-9]+' | "
        "grep -E 'bash|zsh|sh|fish' | tail -n 1 | awk '{print $1}'); "
        "if [ -n \"$pts_pid\" ] && [ -d \"/proc/$pts_pid/cwd\" ]; then "
        "readlink -f /proc/$pts_pid/cwd 2>/dev/null || pwd; "
        "else pwd; fi"
    )

    cmd = [
        ssh_bin,
        "-o", "BatchMode=yes",
        "-o", "ConnectTimeout=3",
        "-o", "StrictHostKeyChecking=accept-new",
        "-p", str(port),
    ]
    if key_path and os.path.isfile(key_path):
        cmd.extend(["-i", key_path])

    cmd.append(f"{user}@{host}")
    cmd.append(probe_script)

    try:
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if res.returncode == 0:
            out = res.stdout.strip()
            if out and out.startswith("/"):
                return out
    except Exception:
        pass

    return "~"


def check_remote_file_exists(
    remote_path: str,
    host: str,
    user: str = "root",
    port: int = 22,
    key_path: Optional[str] = None,
    timeout: int = 3,
) -> bool:
    """
    Checks if a file or directory already exists at remote_path.
    Returns True if exists, False otherwise.
    """
    ssh_bin = _resolve_ssh_bin()
    clean_path = remote_path.replace("'", "'\\''")
    probe_cmd = f"test -e '{clean_path}' && echo EXISTS || echo NOT_EXISTS"

    cmd = [
        ssh_bin,
        "-o", "BatchMode=yes",
        "-o", "ConnectTimeout=3",
        "-o", "StrictHostKeyChecking=accept-new",
        "-p", str(port),
    ]
    if key_path and os.path.isfile(key_path):
        cmd.extend(["-i", key_path])

    cmd.append(f"{user}@{host}")
    cmd.append(probe_cmd)

    try:
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if res.returncode == 0 and "EXISTS" in res.stdout:
            return True
    except Exception:
        pass

    return False


def execute_scp_upload(
    local_path: str,
    remote_dest: str,
    host: str,
    user: str = "root",
    port: int = 22,
    key_path: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Executes SCP upload from local_path to remote_dest on host.
    Returns (success: bool, message: str).
    """
    clean_local = os.path.expanduser(local_path.strip().strip("'\""))
    if not os.path.exists(clean_local):
        return False, f"Local file does not exist: {local_path}"

    scp_bin = _resolve_scp_bin()
    cmd = [
        scp_bin,
        "-P", str(port),
        "-o", "StrictHostKeyChecking=accept-new",
    ]
    if key_path and os.path.isfile(key_path):
        cmd.extend(["-i", key_path])

    # If it is a directory, add recursive flag -r
    if os.path.isdir(clean_local):
        cmd.append("-r")

    cmd.append(clean_local)
    cmd.append(f"{user}@{host}:{remote_dest}")

    try:
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
        )
        if res.returncode == 0:
            return True, "Upload completed successfully."
        err = res.stderr.strip() or res.stdout.strip() or f"SCP exited with code {res.returncode}"
        return False, err
    except Exception as e:
        return False, str(e)
