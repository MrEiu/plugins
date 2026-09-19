"""
System Hardware and OS Information for Help Plugin.
Queries operating system, architecture, kernel, CPU, and memory stats.
All comments and docstrings are in English.
"""

import os
from pathlib import Path
import platform
import shutil
import socket
import subprocess
import sys
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table


def get_system_summary() -> Dict[str, str]:
    """Collects system details using standard library."""
    data = {
        "OS": f"{platform.system()} {platform.release()} ({platform.version()})",
        "Architecture": platform.machine(),
        "Hostname": socket.gethostname(),
        "Processor": platform.processor() or "Unknown CPU",
        "CPU Cores": str(os.cpu_count() or "Unknown"),
        "Python": f"{platform.python_implementation()} {platform.python_version()}",
    }

    # Try memory info
    try:
        if sys.platform == "win32":
            res = subprocess.run(
                ["wmic", "OS", "get", "FreePhysicalMemory,TotalVisibleMemorySize", "/Value"],
                capture_output=True,
                text=True,
                errors="replace",
            )
            if res.returncode == 0:
                lines = dict([l.strip().split("=") for l in res.stdout.strip().splitlines() if "=" in l])
                total_kb = int(lines.get("TotalVisibleMemorySize", 0))
                free_kb = int(lines.get("FreePhysicalMemory", 0))
                if total_kb > 0:
                    used_gb = (total_kb - free_kb) / (1024 * 1024)
                    total_gb = total_kb / (1024 * 1024)
                    data["Memory"] = f"{used_gb:.1f} GB / {total_gb:.1f} GB ({((total_kb - free_kb) / total_kb) * 100:.0f}% used)"
        else:
            if Path("/proc/meminfo").exists():
                meminfo = {}
                with open("/proc/meminfo", "r") as f:
                    for line in f:
                        parts = line.split(":")
                        if len(parts) == 2:
                            meminfo[parts[0].strip()] = parts[1].strip()
                total_kb = int(meminfo.get("MemTotal", "0 kB").split()[0])
                free_kb = int(meminfo.get("MemAvailable", "0 kB").split()[0])
                if total_kb > 0:
                    used_gb = (total_kb - free_kb) / (1024 * 1024)
                    total_gb = total_kb / (1024 * 1024)
                    data["Memory"] = f"{used_gb:.1f} GB / {total_gb:.1f} GB"
    except Exception:
        pass

    return data


def handle_sysinfo(args: List[str], console: Optional[Console] = None) -> int:
    """
    Handles 'kps help sys' or auto-inferred 'help sys' / 'help os'
    """
    con = console or Console(legacy_windows=False)

    # If fastfetch is installed, delegate directly
    fastfetch_bin = shutil.which("fastfetch")
    if fastfetch_bin:
        try:
            return subprocess.run([fastfetch_bin] + args).returncode
        except Exception:
            pass

    info = get_system_summary()

    table = Table(box=None, show_header=False, padding=(0, 2))
    table.add_column("Key", style="bold #00f0ff", width=16)
    table.add_column("Value", style="bold white")

    for k, v in info.items():
        table.add_row(k, v)

    panel = Panel(
        table,
        title="🖥️  System Specification & Status",
        border_style="cyan",
        subtitle="[dim]Powered by Kapsel Platform Engine[/dim]",
    )
    con.print(panel)
    return 0
