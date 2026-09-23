"""
Smart Task Scheduler and Dispatcher for Kapsel Queue.
Manages pending queue, evaluates system redundancy via look.py,
matches and substitutes multi-GPU {gpu} parameters with idle GPUs,
and dispatches tasks to Pueue.
All comments and descriptions are in English.
"""

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from kapsel.storage.config import get_kapsel_dir
from .look import find_available_idle_gpus, is_system_redundant, probe_all_gpus


@dataclass
class PendingTask:
    id: str
    command_template: str
    condition: Optional[str] = None
    created_at: float = 0.0
    status: str = "pending"
    allocated_gpu: Optional[int] = None
    dispatched_at: Optional[float] = None
    pueue_id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PendingTask":
        return cls(
            id=data.get("id", ""),
            command_template=data.get("command_template", ""),
            condition=data.get("condition"),
            created_at=data.get("created_at", 0.0),
            status=data.get("status", "pending"),
            allocated_gpu=data.get("allocated_gpu"),
            dispatched_at=data.get("dispatched_at"),
            pueue_id=data.get("pueue_id"),
        )


def _get_queue_data_dir() -> Path:
    """Returns directory path for queue persistent state."""
    d = get_kapsel_dir() / "plugins_data" / "queue"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _get_state_file() -> Path:
    return _get_queue_data_dir() / "scheduler_state.json"


def load_state() -> Dict[str, Any]:
    """Loads scheduler configuration, pending tasks, and GPU allocation ledger."""
    f = _get_state_file()
    if f.is_file():
        try:
            with open(f, "r", encoding="utf-8") as fp:
                data = json.load(fp)
                if isinstance(data, dict):
                    data.setdefault("max_running", 4)
                    data.setdefault("interval_seconds", 5)
                    data.setdefault(
                        "thresholds",
                        {
                            "min_free_cpu": "15%",
                            "min_free_ram": "0.5GB",
                            "min_free_vram": "15%",
                        },
                    )
                    data.setdefault("pending", [])
                    data.setdefault("active_allocations", {})  # {str(pueue_id): gpu_idx}
                    return data
        except Exception:
            pass

    default_state = {
        "max_running": 4,
        "interval_seconds": 5,
        "thresholds": {
            "min_free_cpu": "15%",
            "min_free_ram": "0.5GB",
            "min_free_vram": "15%",
        },
        "pending": [],
        "active_allocations": {},
    }
    save_state(default_state)
    return default_state


def save_state(state: Dict[str, Any]) -> None:
    """Saves scheduler state to disk atomically."""
    f = _get_state_file()
    tmp = f.with_suffix(".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as fp:
            json.dump(state, fp, indent=2, ensure_ascii=False)
        tmp.replace(f)
    except Exception:
        if tmp.exists():
            try:
                tmp.unlink()
            except Exception:
                pass


def get_max_running() -> int:
    return int(load_state().get("max_running", 4))


def set_max_running(limit: int) -> None:
    state = load_state()
    state["max_running"] = max(1, limit)
    save_state(state)


def get_check_interval() -> int:
    return int(load_state().get("interval_seconds", 5))


def set_check_interval(seconds: int) -> None:
    state = load_state()
    state["interval_seconds"] = max(1, seconds)
    save_state(state)


def get_thresholds() -> Dict[str, Any]:
    return load_state().get(
        "thresholds",
        {
            "min_free_cpu": "15%",
            "min_free_ram": "0.5GB",
            "min_free_vram": "15%",
        },
    )


def set_threshold(key: str, value: Any) -> None:
    state = load_state()
    th = state.setdefault("thresholds", {})
    th[key] = value
    save_state(state)


def get_config() -> Dict[str, Any]:
    state = load_state()
    th = state.get("thresholds", {})
    return {
        "max_running": state.get("max_running", 4),
        "interval_seconds": state.get("interval_seconds", 5),
        "min_free_ram": th.get("min_free_ram", "0.5GB"),
        "min_free_vram": th.get("min_free_vram", "15%"),
        "min_free_cpu": th.get("min_free_cpu", "15%"),
    }


def update_config(updates: Dict[str, Any]) -> Dict[str, Any]:
    state = load_state()
    th = state.setdefault("thresholds", {})

    for k, v in updates.items():
        k_clean = k.lower().replace("-", "_")
        if k_clean in ("max_running", "limit"):
            state["max_running"] = max(1, int(v))
        elif k_clean in ("interval", "interval_seconds", "tick"):
            state["interval_seconds"] = max(1, int(str(v).lower().rstrip("s")))
        elif k_clean in ("min_ram", "min_free_ram", "ram"):
            th["min_free_ram"] = str(v).strip()
        elif k_clean in ("min_vram", "min_free_vram", "vram", "gpu_vram"):
            th["min_free_vram"] = str(v).strip()
        elif k_clean in ("min_cpu", "min_free_cpu", "cpu"):
            th["min_free_cpu"] = str(v).strip()

    save_state(state)
    return get_config()


def add_pending_task(command_template: str, condition: Optional[str] = None) -> PendingTask:
    """Enqueues a new command template into the pending queue."""
    state = load_state()
    task_num = len(state.get("pending", [])) + int(time.time()) % 10000
    task_id = f"P-{task_num}"

    task = PendingTask(
        id=task_id,
        command_template=command_template.strip(),
        condition=condition.strip() if condition and condition.strip() else None,
        created_at=time.time(),
        status="pending",
    )

    state["pending"].append(task.to_dict())
    save_state(state)
    return task


def list_pending_tasks() -> List[PendingTask]:
    state = load_state()
    return [PendingTask.from_dict(t) for t in state.get("pending", [])]


def remove_pending_task(task_id: str) -> bool:
    state = load_state()
    initial_len = len(state.get("pending", []))
    state["pending"] = [t for t in state.get("pending", []) if t.get("id") != task_id]
    if len(state["pending"]) != initial_len:
        save_state(state)
        return True
    return False


def get_active_allocated_gpus(state: Optional[Dict[str, Any]] = None) -> Set[int]:
    """Returns set of GPU indices currently locked by active Pueue tasks."""
    st = state or load_state()
    allocs = st.get("active_allocations", {})
    return {int(gpu_idx) for gpu_idx in allocs.values()}


def _sync_pueue_status(pueue_bin: str, state: Dict[str, Any]) -> Tuple[int, Set[int]]:
    """
    Queries Pueue daemon status via JSON.
    Releases GPU allocations for tasks that have finished (Done, Failed, Killed).
    Returns (currently_running_task_count, set_of_active_allocated_gpus).
    """
    running_count = 0
    allocations = dict(state.get("active_allocations", {}))  # {str(pueue_id): gpu_idx}

    try:
        res = subprocess.run([pueue_bin, "status", "--json"], capture_output=True, text=True, timeout=2.0)
        if res.returncode == 0:
            pueue_data = json.loads(res.stdout)
            tasks = pueue_data.get("tasks", {})

            active_pueue_ids = set()
            for tid_str, tinfo in tasks.items():
                status = tinfo.get("status", "")
                group = tinfo.get("group", "")
                # Skip internal scheduler worker task if any
                if group == "_scheduler":
                    continue

                if status == "Running":
                    running_count += 1
                    active_pueue_ids.add(str(tid_str))
                elif status in ("Queued", "Paused", "Stashing"):
                    active_pueue_ids.add(str(tid_str))

            # Prune allocations for finished tasks
            for pid in list(allocations.keys()):
                if pid not in active_pueue_ids:
                    allocations.pop(pid, None)

            state["active_allocations"] = allocations
    except Exception:
        pass

    active_gpus = {int(v) for v in allocations.values()}
    return running_count, active_gpus


def _evaluate_extra_condition(condition_cmd: str) -> bool:
    """Executes the user-specified extra condition. Returns True if exit code == 0."""
    try:
        # Run using default shell with short timeout
        res = subprocess.run(
            condition_cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=5.0,
        )
        return res.returncode == 0
    except Exception:
        return False


def _dispatch_task_to_pueue(
    pueue_bin: str,
    command: str,
) -> Optional[int]:
    """
    Dispatches a concrete formatted command to Pueue.
    Does NOT inject CUDA_VISIBLE_DEVICES into the environment, honoring user instruction.
    Returns created Pueue Task ID.
    """
    cmd = [pueue_bin, "add", "--", command]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5.0)
        if res.returncode == 0:
            match = re.search(r"id\s+(\d+)", res.stdout, re.IGNORECASE)
            if match:
                return int(match.group(1))
            return 0
    except Exception:
        pass
    return None


def tick(pueue_bin: str) -> List[Tuple[PendingTask, int]]:
    """
    Executes one scheduling tick:
    1. Synchronizes active task count and releases finished GPU allocations.
    2. Checks max running concurrency limit.
    3. Evaluates hardware redundancy (look.py) with numerical and percentage thresholds.
    4. Evaluates extra user conditions.
    5. Matches available idle GPUs for commands with '{gpu}' template.
    6. Dispatches ready tasks to Pueue.
    """
    state = load_state()
    max_running = int(state.get("max_running", 4))
    thresholds = state.get("thresholds", {})
    pending_list = state.get("pending", [])
    if not pending_list:
        save_state(state)
        return []

    # 1. Sync Pueue status & prune finished allocations
    running_count, allocated_gpus = _sync_pueue_status(pueue_bin, state)

    dispatched_records: List[Tuple[PendingTask, int]] = []
    remaining_pending: List[Dict[str, Any]] = []

    for task_dict in pending_list:
        task = PendingTask.from_dict(task_dict)

        # Concurrency limit reached
        if running_count >= max_running:
            remaining_pending.append(task_dict)
            continue

        # 2. Check user's extra condition if specified
        if task.condition:
            if not _evaluate_extra_condition(task.condition):
                remaining_pending.append(task_dict)
                continue

        # 3. Check GPU requirement ({gpu} or {GPU} in command)
        has_gpu_placeholder = bool(re.search(r"\{gpu\}", task.command_template, re.IGNORECASE))

        if has_gpu_placeholder:
            # Hardware check: System must have healthy CPU/RAM AND an idle GPU
            redundant, _ = is_system_redundant(
                allocated_gpus=allocated_gpus,
                requires_gpu=True,
                thresholds=thresholds,
            )
            if not redundant:
                remaining_pending.append(task_dict)
                continue

            min_vram = thresholds.get("min_free_vram", "15%")
            idle_gpus = find_available_idle_gpus(
                allocated_gpu_indices=allocated_gpus,
                min_free_vram=min_vram,
            )
            if not idle_gpus:
                remaining_pending.append(task_dict)
                continue

            # Pick the GPU with the lowest occupancy (least VRAM and compute load)
            selected_gpu = idle_gpus[0]

            # Replace {gpu} or {GPU} with concrete GPU index
            concrete_cmd = re.sub(r"\{gpu\}", str(selected_gpu), task.command_template, flags=re.IGNORECASE)

            # Dispatch to Pueue (NO CUDA_VISIBLE_DEVICES injected)
            pueue_id = _dispatch_task_to_pueue(pueue_bin, concrete_cmd)
            if pueue_id is not None:
                allocated_gpus.add(selected_gpu)
                state["active_allocations"][str(pueue_id)] = selected_gpu
                running_count += 1
                task.allocated_gpu = selected_gpu
                task.pueue_id = pueue_id
                task.status = "running"
                task.dispatched_at = time.time()
                dispatched_records.append((task, pueue_id))
            else:
                remaining_pending.append(task_dict)
        else:
            # Pure CPU/generic task: Needs CPU and RAM redundancy
            redundant, _ = is_system_redundant(
                allocated_gpus=allocated_gpus,
                requires_gpu=False,
                thresholds=thresholds,
            )
            if not redundant:
                remaining_pending.append(task_dict)
                continue

            # Dispatch to Pueue
            pueue_id = _dispatch_task_to_pueue(pueue_bin, task.command_template)
            if pueue_id is not None:
                running_count += 1
                task.pueue_id = pueue_id
                task.status = "running"
                task.dispatched_at = time.time()
                dispatched_records.append((task, pueue_id))
            else:
                remaining_pending.append(task_dict)

    state["pending"] = remaining_pending
    save_state(state)
    return dispatched_records


def run_scheduler_daemon_loop(pueue_bin: str) -> None:
    """
    Autonomous scheduler loop supervised by Pueue.
    Runs tick() periodically based on configured interval_seconds.
    """
    while True:
        try:
            interval = get_check_interval()
            tick(pueue_bin)
            time.sleep(interval)
        except KeyboardInterrupt:
            break
        except Exception:
            time.sleep(5)


if __name__ == "__main__":
    from .plugin import _resolve_pueue_executables
    pueue_exec, _ = _resolve_pueue_executables()
    if pueue_exec:
        run_scheduler_daemon_loop(pueue_exec)
