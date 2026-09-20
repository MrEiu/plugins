"""
Kapsel kssh Plugin - Port Forwarding & Tunnel Manager.
Supports dynamic forward tunneling (Remote -> Local, default) and reverse tunneling (Local -> Remote, prefixed with 'r').
Maintains lifecycle of background tunnel processes and terminates them upon session close.
All comments and docstrings are in English.
"""

from dataclasses import dataclass
import os
import re
import shutil
import subprocess
import sys
from typing import Dict, List, Optional, Tuple


@dataclass
class TunnelInfo:
    mode: str  # "L" (Remote->Local) or "R" (Local->Remote)
    local_port: int
    remote_port: int
    host: str
    pid: int
    process: subprocess.Popen
    description: str


class TunnelManager:
    """Manages active SSH forwarding tunnel subprocesses."""

    def __init__(self):
        self._active_tunnels: List[TunnelInfo] = []

    @property
    def active_tunnels(self) -> List[TunnelInfo]:
        """Returns list of running tunnels, pruning terminated ones."""
        running = []
        for t in self._active_tunnels:
            if t.process.poll() is None:
                running.append(t)
        self._active_tunnels = running
        return list(self._active_tunnels)

    @staticmethod
    def parse_tunnel_spec(raw_input: str) -> Optional[Tuple[str, int, int]]:
        """
        Parses user tunnel specification string:
        - '3306' -> mode 'L', local 3306, remote 3306 (remote -> local)
        - '8080:3306' -> mode 'L', local 8080, remote 3306
        - 'r 8000' or 'r8000' -> mode 'R', local 8000, remote 8000 (local -> remote reverse)
        - 'r 9000:8000' -> mode 'R', remote 9000, local 8000
        Returns (mode, local_port, remote_port) or None if invalid.
        """
        text = raw_input.strip()
        if not text:
            return None

        is_reverse = False
        if text.lower().startswith("r"):
            is_reverse = True
            text = text[1:].strip()

        if not text:
            return None

        # Matches: "3306" or "8080:3306"
        m = re.match(r"^(\d+)(?::(\d+))?$", text)
        if not m:
            return None

        p1 = int(m.group(1))
        p2 = int(m.group(2)) if m.group(2) else p1

        if not (1 <= p1 <= 65535 and 1 <= p2 <= 65535):
            return None

        if is_reverse:
            # For reverse: remote port receives traffic and forwards to local port
            # 'r 8000' -> remote 8000 -> local 8000
            # 'r 9000:8000' -> remote 9000 -> local 8000
            remote_port = p1
            local_port = p2
            return ("R", local_port, remote_port)
        else:
            # For forward: local port receives traffic and forwards to remote port
            # '3306' -> local 3306 -> remote 3306
            # '8080:3306' -> local 8080 -> remote 3306
            local_port = p1
            remote_port = p2
            return ("L", local_port, remote_port)

    def start_tunnel(
        self,
        spec_str: str,
        host: str,
        user: str = "root",
        ssh_port: int = 22,
        key_path: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """
        Launches a background SSH forwarding tunnel based on user input.
        Returns (success: bool, status_message: str).
        """
        parsed = self.parse_tunnel_spec(spec_str)
        if not parsed:
            return False, f"Invalid port format: '{spec_str}'. Use '3306' (remote->local) or 'r 8000' (local->remote)."

        mode, local_port, remote_port = parsed
        ssh_bin = shutil.which("ssh") or "ssh"

        cmd = [
            ssh_bin,
            "-N",  # Do not execute a remote command
            "-o", "ExitOnForwardFailure=yes",
            "-o", "StrictHostKeyChecking=accept-new",
            "-p", str(ssh_port),
        ]
        if key_path and os.path.isfile(key_path):
            cmd.extend(["-i", key_path])

        if mode == "L":
            cmd.extend(["-L", f"{local_port}:127.0.0.1:{remote_port}"])
            desc = f"Local localhost:{local_port} -> Remote {remote_port}"
        else:
            cmd.extend(["-R", f"{remote_port}:127.0.0.1:{local_port}"])
            desc = f"Remote localhost:{remote_port} -> Local {local_port} (Reverse)"

        cmd.append(f"{user}@{host}")

        creationflags = 0
        if sys.platform == "win32":
            creationflags = subprocess.CREATE_NO_WINDOW

        try:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                creationflags=creationflags,
            )

            # Give it a brief moment to catch immediate port binding failures
            try:
                ret = proc.wait(timeout=0.6)
                err = proc.stderr.read().decode("utf-8", errors="replace").strip() if proc.stderr else ""
                return False, f"Tunnel failed (code {ret}): {err or 'Port might already be in use'}"
            except subprocess.TimeoutExpired:
                # Still running, tunnel successfully established!
                pass

            info = TunnelInfo(
                mode=mode,
                local_port=local_port,
                remote_port=remote_port,
                host=host,
                pid=proc.pid,
                process=proc,
                description=desc,
            )
            self._active_tunnels.append(info)
            return True, f"Tunnel active: {desc} (PID {proc.pid})"

        except Exception as e:
            return False, f"Failed to start tunnel: {e}"

    def stop_all(self) -> None:
        """Terminates all active tunnel processes."""
        for t in self._active_tunnels:
            try:
                if t.process.poll() is None:
                    t.process.terminate()
                    try:
                        t.process.wait(timeout=1.0)
                    except subprocess.TimeoutExpired:
                        t.process.kill()
            except Exception:
                pass
        self._active_tunnels.clear()


# Global singleton instance for current session
tunnel_manager = TunnelManager()
