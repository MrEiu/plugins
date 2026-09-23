"""
Resource Probe and Inspection Module for Kapsel Queue.
Detects CPU utilization, system RAM redundancy, and detailed multi-GPU VRAM/utilization.
Supports both numerical minimum free amounts (e.g. '0.5GB', '1024MB') and percentage (e.g. '15%').
All comments and descriptions are in English.
"""

from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple, Union

import psutil
from rich.console import Console
from rich.panel import Panel
from rich.table import Table


def parse_threshold(
    val: Any,
    total_amount: float,
    default_unit: str = "GB",
) -> Tuple[bool, float, str]:
    """
    Parses a minimum free threshold that can be a percentage or numerical value.
    Returns (is_percentage, threshold_value, display_str).
    - Percentage (e.g. '15%', 15.0 with default_unit='%'):
        is_percentage = True, threshold_value = 15.0, display = '15%'
    - Numerical value (e.g. '1.5GB', '1500MB', '2G', or float in GB):
        is_percentage = False, threshold_value = in GB, display = '1.5 GB'
    """
    if val is None:
        val = "10%"

    if isinstance(val, (int, float)):
        if 0.0 < val <= 1.0 and default_unit == "%":
            return True, val * 100.0, f"{val * 100.0:.0f}%"
        if default_unit == "%":
            return True, float(val), f"{float(val):.0f}%"
        return False, float(val), f"{float(val):.1f} {default_unit}"

    s = str(val).strip().lower()
    if s.endswith("%"):
        try:
            num = float(s.rstrip("%").strip())
            return True, num, f"{num:.0f}%"
        except ValueError:
            return True, 10.0, "10%"

    if s.endswith("gb") or s.endswith("g"):
        try:
            num = float(re.sub(r"[^\d.]", "", s))
            return False, num, f"{num:.1f} GB"
        except ValueError:
            return False, 0.5, "0.5 GB"

    if s.endswith("mb") or s.endswith("m"):
        try:
            num = float(re.sub(r"[^\d.]", "", s))
            num_gb = num / 1024.0
            return False, num_gb, f"{num:.0f} MB"
        except ValueError:
            return False, 0.5, "512 MB"

    try:
        num = float(s)
        if default_unit == "%" or (0.0 < num <= 1.0):
            return True, (num * 100.0 if num <= 1.0 else num), f"{num:.0f}%"
        return False, num, f"{num:.1f} {default_unit}"
    except ValueError:
        return True, 10.0, "10%"


def check_resource_free(
    free_amount_gb: float,
    total_amount_gb: float,
    threshold: Any,
    default_unit: str = "GB",
) -> Tuple[bool, str]:
    """
    Checks if remaining/free resource satisfies the minimum threshold.
    Supports both numerical threshold (e.g. '1.0GB', '500MB') and percentage (e.g. '15%').
    Returns (is_satisfied, formatted_threshold_string).
    """
    is_pct, thresh_val, disp = parse_threshold(threshold, total_amount_gb, default_unit=default_unit)
    if total_amount_gb <= 0:
        return False, disp

    if is_pct:
        free_pct = (free_amount_gb / total_amount_gb) * 100.0
        return free_pct >= thresh_val, disp
    else:
        return free_amount_gb >= thresh_val, disp


class GPUInfo:
    """Represents the status and metrics of a single physical GPU."""

    def __init__(
        self,
        index: int,
        name: str,
        total_vram_mb: float,
        used_vram_mb: float,
        free_vram_mb: float,
        utilization_gpu: float,
    ) -> None:
        self.index = index
        self.name = name
        self.total_vram_mb = total_vram_mb
        self.used_vram_mb = used_vram_mb
        self.free_vram_mb = free_vram_mb
        self.utilization_gpu = utilization_gpu

    @property
    def free_vram_gb(self) -> float:
        return self.free_vram_mb / 1024.0

    @property
    def total_vram_gb(self) -> float:
        return self.total_vram_mb / 1024.0

    @property
    def used_vram_gb(self) -> float:
        return self.used_vram_mb / 1024.0

    @property
    def free_vram_percent(self) -> float:
        if self.total_vram_mb <= 0:
            return 0.0
        return (self.free_vram_mb / self.total_vram_mb) * 100.0

    @property
    def vram_used_percent(self) -> float:
        if self.total_vram_mb <= 0:
            return 0.0
        return (self.used_vram_mb / self.total_vram_mb) * 100.0

    def is_idle(
        self,
        min_free_vram: Any = "15%",
        max_util_percent: float = 15.0,
    ) -> bool:
        """
        Determines whether the GPU is idle and available for new tasks.
        Compatible with both numerical values (e.g. '1.5GB', '1024MB') and percentage (e.g. '15%').
        """
        vram_ok, _ = check_resource_free(self.free_vram_gb, self.total_vram_gb, min_free_vram, default_unit="GB")
        util_ok = self.utilization_gpu <= max_util_percent
        return vram_ok and util_ok


def probe_cpu(min_free_cpu: Any = "15%") -> Dict[str, Any]:
    """
    Probes system CPU usage percentage and evaluates minimum free CPU.
    Compatible with percentage threshold (e.g. '15%' free, meaning CPU <= 85%).
    """
    percent = psutil.cpu_percent(interval=None)
    free_percent = max(0.0, 100.0 - percent)
    logical_cores = psutil.cpu_count(logical=True) or 1
    physical_cores = psutil.cpu_count(logical=False) or logical_cores

    is_pct, thresh_val, disp = parse_threshold(min_free_cpu, 100.0, default_unit="%")
    redundant = free_percent >= thresh_val
    return {
        "percent": percent,
        "free_percent": free_percent,
        "logical_cores": logical_cores,
        "physical_cores": physical_cores,
        "redundant": redundant,
        "threshold_display": disp,
    }


def probe_memory(min_free_ram: Any = "0.5GB") -> Dict[str, Any]:
    """
    Probes system RAM capacity, available memory, and evaluates minimum remaining memory.
    Compatible with both numerical values (e.g. '0.5GB', '512MB') and percentage (e.g. '5%', '10%').
    """
    vm = psutil.virtual_memory()
    total_gb = vm.total / (1024.0**3)
    available_gb = vm.available / (1024.0**3)
    used_gb = vm.used / (1024.0**3)
    free_percent = (available_gb / total_gb * 100.0) if total_gb > 0 else 0.0

    redundant, disp = check_resource_free(available_gb, total_gb, min_free_ram, default_unit="GB")
    return {
        "total_gb": total_gb,
        "available_gb": available_gb,
        "used_gb": used_gb,
        "percent": vm.percent,
        "free_percent": free_percent,
        "redundant": redundant,
        "threshold_display": disp,
    }


def probe_all_gpus() -> List[GPUInfo]:
    """
    Scans and probes all NVIDIA GPUs using nvidia-smi.
    Returns a list of GPUInfo objects for GPU 0, 1, 2, 3...
    If no NVIDIA GPUs are present, returns an empty list gracefully.
    """
    gpus: List[GPUInfo] = []
    nvidia_smi = shutil.which("nvidia-smi")
    if not nvidia_smi:
        return gpus

    cmd = [
        nvidia_smi,
        "--query-gpu=index,name,memory.total,memory.used,memory.free,utilization.gpu",
        "--format=csv,noheader,nounits",
    ]

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
        if res.returncode != 0:
            return gpus

        for line in res.stdout.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 6:
                try:
                    idx = int(parts[0])
                    name = parts[1]
                    total_mb = float(parts[2])
                    used_mb = float(parts[3])
                    free_mb = float(parts[4])
                    util_gpu = float(parts[5])
                    gpus.append(
                        GPUInfo(
                            index=idx,
                            name=name,
                            total_vram_mb=total_mb,
                            used_vram_mb=used_mb,
                            free_vram_mb=free_mb,
                            utilization_gpu=util_gpu,
                        )
                    )
                except ValueError:
                    continue
    except Exception:
        pass

    return gpus


def find_available_idle_gpus(
    allocated_gpu_indices: Optional[set[int]] = None,
    min_free_vram: Any = "15%",
    max_util_percent: float = 15.0,
) -> List[int]:
    """
    Finds all physically available and idle GPU indices that satisfy minimum remaining VRAM
    (numerical or percentage) and are not locked by currently executing queue tasks.
    Returns GPU indices sorted by lowest occupancy (least VRAM used % and core utilization first).
    """
    allocated = allocated_gpu_indices or set()
    all_gpus = probe_all_gpus()
    idle_gpus: List[GPUInfo] = []

    for gpu in all_gpus:
        if gpu.index in allocated:
            continue
        if gpu.is_idle(min_free_vram=min_free_vram, max_util_percent=max_util_percent):
            idle_gpus.append(gpu)

    # Sort available GPUs by lowest occupancy (least loaded first):
    # 1. Lower VRAM usage percentage (or used MB)
    # 2. Lower core utilization percentage
    # 3. Higher absolute free VRAM
    # 4. GPU index (tie-breaker)
    idle_gpus.sort(
        key=lambda g: (
            g.vram_used_percent,
            g.utilization_gpu,
            -g.free_vram_mb,
            g.index,
        )
    )

    return [g.index for g in idle_gpus]


def is_system_redundant(
    allocated_gpus: Optional[set[int]] = None,
    requires_gpu: bool = False,
    thresholds: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, str]:
    """
    Evaluates whether the host system currently has sufficient redundant resources
    to dispatch a new command.
    Checks minimum remaining free resources supporting both numerical values and percentages.
    """
    th = thresholds or {}
    min_cpu = th.get("min_free_cpu", "15%")
    min_ram = th.get("min_free_ram", "0.5GB")
    min_vram = th.get("min_free_vram", "15%")

    cpu = probe_cpu(min_free_cpu=min_cpu)
    mem = probe_memory(min_free_ram=min_ram)

    if not cpu["redundant"]:
        return False, f"CPU free below minimum ({cpu['free_percent']:.1f}% free < {cpu['threshold_display']})"

    if not mem["redundant"]:
        return False, f"RAM free below minimum ({mem['available_gb']:.1f} GB / {mem['free_percent']:.1f}% < {mem['threshold_display']})"

    if requires_gpu:
        idle_gpus = find_available_idle_gpus(allocated_gpus, min_free_vram=min_vram)
        if not idle_gpus:
            all_gpus = probe_all_gpus()
            if not all_gpus:
                return False, "No GPU detected on system"
            return False, f"All GPUs busy or below VRAM threshold ({min_vram})"

    return True, "Resources healthy and redundant"


def render_look_dashboard(
    console: Optional[Console] = None,
    allocated_gpus: Optional[set[int]] = None,
    thresholds: Optional[Dict[str, Any]] = None,
) -> int:
    """Renders the comprehensive 'kps queue look' hardware redundancy dashboard."""
    con = console or Console(legacy_windows=False)
    allocated = allocated_gpus or set()

    th = thresholds or {}
    min_cpu = th.get("min_free_cpu", "15%")
    min_ram = th.get("min_free_ram", "0.5GB")
    min_vram = th.get("min_free_vram", "15%")

    cpu = probe_cpu(min_free_cpu=min_cpu)
    mem = probe_memory(min_free_ram=min_ram)
    gpus = probe_all_gpus()

    cpu_color = "#10b981" if cpu["redundant"] else "#f43f5e"
    mem_color = "#10b981" if mem["redundant"] else "#f43f5e"

    table = Table.grid(padding=(0, 2))
    table.add_column("Category", style="bold #00f0ff", no_wrap=True)
    table.add_column("Metrics", style="white")
    table.add_column("Min Free Req", style="dim")
    table.add_column("Redundancy", justify="right")

    # CPU Row
    cpu_bar_len = int(cpu["percent"] / 5)
    cpu_bar = f"[{cpu_color}]{'█' * cpu_bar_len}{'░' * (20 - cpu_bar_len)}[/]"
    cpu_status = f"[{cpu_color}]{'🟢 Healthy' if cpu['redundant'] else '🔴 Busy'}[/]"
    table.add_row(
        "CPU",
        f"{cpu['percent']:.1f}% {cpu_bar} ({cpu['free_percent']:.1f}% free, {cpu['logical_cores']} cores)",
        f">= {cpu['threshold_display']}",
        cpu_status,
    )

    # Memory Row
    mem_bar_len = int(mem["percent"] / 5)
    mem_bar = f"[{mem_color}]{'█' * mem_bar_len}{'░' * (20 - mem_bar_len)}[/]"
    mem_status = f"[{mem_color}]{'🟢 Healthy' if mem['redundant'] else '🔴 Low'}[/]"
    table.add_row(
        "Memory (RAM)",
        f"{mem['used_gb']:.1f} / {mem['total_gb']:.1f} GB ({mem['available_gb']:.1f} GB / {mem['free_percent']:.1f}% free) {mem_bar}",
        f">= {mem['threshold_display']}",
        mem_status,
    )

    # GPU Rows
    if gpus:
        for gpu in gpus:
            is_alloc = gpu.index in allocated
            is_idle = gpu.is_idle(min_free_vram=min_vram) and not is_alloc

            gpu_color = "#10b981" if is_idle else ("#f59e0b" if is_alloc else "#f43f5e")
            bar_len = int(gpu.vram_used_percent / 5)
            gpu_bar = f"[{gpu_color}]{'█' * bar_len}{'░' * (20 - bar_len)}[/]"

            if is_alloc:
                status_badge = "[#f59e0b]🟡 In Queue Task[/]"
            elif is_idle:
                status_badge = "[#10b981]🟢 Idle / Ready[/]"
            else:
                status_badge = "[#f43f5e]🔴 Busy[/]"

            table.add_row(
                f"GPU {gpu.index}",
                f"{gpu.name} | VRAM: {gpu.used_vram_gb:.1f} / {gpu.total_vram_gb:.1f} GB ({gpu.free_vram_gb:.1f} GB / {gpu.free_vram_percent:.1f}% free) {gpu_bar} (Util: {gpu.utilization_gpu:.0f}%)",
                f">= {min_vram}",
                status_badge,
            )
    else:
        table.add_row("GPU", "[dim]No dedicated NVIDIA GPU detected or nvidia-smi unavailable[/]", "-", "[dim]N/A[/]")

    # Overall Summary
    healthy, reason = is_system_redundant(allocated, thresholds=th)
    overall_color = "#10b981" if healthy else "#f59e0b"
    summary_text = (
        f"[{overall_color}]● Status:[/] {reason}  "
        f"[dim](Min free thresholds: CPU >= {cpu['threshold_display']}, RAM >= {mem['threshold_display']}, GPU >= {min_vram})[/]"
    )

    panel = Panel(
        table,
        title="[bold #00f0ff]🔍 Environment Redundancy & Hardware Probe (kps queue look)[/]",
        subtitle=summary_text,
        border_style="#38bdf8",
        padding=(1, 2),
    )
    con.print(panel)
    return 0
