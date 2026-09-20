"""
Concurrent Multi-Manager Streaming Search for Kapsel Install Plugin.
Executes parallel searches across available host package managers via MPM,
streaming results dynamically to a live-updating Rich terminal table.

All comments and docstrings are in English.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text


@dataclass
class SearchItem:
    package_id: str
    name: Optional[str]
    manager: str
    version: Optional[str]
    description: Optional[str]
    priority: int = 50
    is_recommended: bool = False

    @property
    def display_name(self) -> str:
        return self.name or self.package_id


# Platform priority weights (higher weight = higher priority)
PLATFORM_MANAGER_WEIGHTS: Dict[str, Dict[str, int]] = {
    "windows": {
        "scoop": 100,
        "winget": 90,
        "choco": 80,
        "vcpkg": 75,
        "uv": 70,
        "pipx": 65,
        "cargo": 60,
        "npm": 55,
        "pnpm": 50,
        "pip": 10,
    },
    "macos": {
        "brew": 100,
        "mas": 90,
        "uv": 80,
        "pipx": 75,
        "cargo": 70,
        "npm": 65,
        "pnpm": 60,
        "gem": 55,
        "pip": 10,
    },
    "linux": {
        "pacman": 100,
        "yay": 95,
        "paru": 95,
        "apt": 100,
        "dnf": 100,
        "zypper": 100,
        "flatpak": 85,
        "snap": 80,
        "uv": 75,
        "pipx": 70,
        "cargo": 65,
        "npm": 60,
        "pnpm": 55,
        "pip": 10,
    },
}


def get_platform_weights() -> Dict[str, int]:
    """Returns manager priority weights for the current host OS."""
    if sys.platform == "win32":
        return PLATFORM_MANAGER_WEIGHTS["windows"]
    if sys.platform == "darwin":
        return PLATFORM_MANAGER_WEIGHTS["macos"]
    return PLATFORM_MANAGER_WEIGHTS["linux"]


def get_manager_weight(manager_id: str) -> int:
    """Calculates sorting weight for a given manager."""
    weights = get_platform_weights()
    return weights.get(manager_id.lower(), 40)


def execute_manager_search(
    mpm_exec: List[str],
    manager: str,
    query: str,
    timeout: int = 45,
) -> Tuple[str, List[SearchItem], Optional[str]]:
    """
    Executes a single manager search query using mpm.
    Returns (manager, items, error_message).
    """
    cmd = mpm_exec + [
        "--table-format", "json",
        "--description",
        f"--{manager}",
        "search",
        query,
    ]

    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=env,
        )

        stdout = proc.stdout.strip()
        if not stdout:
            return manager, [], None

        # Parse JSON output from MPM
        try:
            data = json.loads(stdout)
        except Exception:
            # If stdout contains non-json headers, find first '{'
            idx = stdout.find("{")
            if idx != -1:
                data = json.loads(stdout[idx:])
            else:
                return manager, [], None

        items: List[SearchItem] = []
        weight = get_manager_weight(manager)

        if isinstance(data, dict):
            # MPM JSON schema: {manager_id: {"packages": [...]}}
            mgr_entry = data.get(manager, {})
            packages = mgr_entry.get("packages", []) if isinstance(mgr_entry, dict) else []
            for pkg in packages:
                pkg_id = pkg.get("id") or pkg.get("package_id")
                if not pkg_id:
                    continue
                item = SearchItem(
                    package_id=str(pkg_id),
                    name=pkg.get("name"),
                    manager=manager,
                    version=pkg.get("latest_version") or pkg.get("version"),
                    description=pkg.get("description"),
                    priority=weight,
                )
                items.append(item)

        return manager, items, None

    except subprocess.TimeoutExpired:
        return manager, [], f"Timed out after {timeout}s"
    except Exception as e:
        return manager, [], str(e)


def build_results_table(
    items: List[SearchItem],
    in_progress: Set[str],
    completed: Dict[str, int],
    query: str,
    max_per_manager: int = 3,
) -> Table:
    """Renders the Rich Live Table grouping results by manager with top 3 per manager limit."""
    table = Table(
        title=f"📦 Multi-Manager Search for '[bold #00f0ff]{query}[/]' (Top 3 per manager)",
        title_style="bold white",
        border_style="bright_blue",
        header_style="bold #38bdf8",
        box=None,
    )
    table.add_column("Manager", style="cyan", width=12)
    table.add_column("Package ID", style="bold white", width=26)
    table.add_column("Version", style="green", width=14)
    table.add_column("Description", style="dim", overflow="ellipsis")
    table.add_column("Recommendation", justify="center", width=16)

    # Group items by manager
    grouped: Dict[str, List[SearchItem]] = {}
    for item in items:
        grouped.setdefault(item.manager, []).append(item)

    # Order managers by platform priority weight
    ordered_mgrs = sorted(grouped.keys(), key=get_manager_weight, reverse=True)

    # Sort each manager's items (exact match / priority first)
    has_recommended = False
    for mgr in ordered_mgrs:
        mgr_items = sorted(
            grouped[mgr],
            key=lambda x: (1 if x.package_id.lower() == query.lower() else 0, x.priority),
            reverse=True,
        )
        for it in mgr_items[:max_per_manager]:
            rec_text = ""
            if not has_recommended and (it.package_id.lower() == query.lower() or it.priority >= 90):
                it.is_recommended = True
                rec_text = "[bold #10b981]★ RECOMMENDED[/]"
                has_recommended = True

            table.add_row(
                it.manager,
                it.package_id,
                it.version or "-",
                it.description or "-",
                rec_text,
            )

        if len(mgr_items) > max_per_manager:
            hidden_cnt = len(mgr_items) - max_per_manager
            table.add_row(
                f"[dim]{mgr}[/]",
                f"[dim italic]... +{hidden_cnt} more (expandable)[/]",
                "-",
                f"[dim]Total {len(mgr_items)} packages found in {mgr}[/]",
                "",
            )

    # If table has no rows yet, provide scanning status
    if not items:
        status_str = f"Scanning {len(in_progress)} package managers..." if in_progress else "No results yet."
        table.add_row("-", "searching...", "-", status_str, "")

    return table


def concurrent_streaming_search(
    mpm_exec: List[str],
    managers: List[str],
    query: str,
    console: Optional[Console] = None,
    timeout_per_manager: int = 40,
) -> List[SearchItem]:
    """
    Executes concurrent multi-manager search with Rich Live streaming progress.
    Uses transient display so it seamlessly transitions to the single selection view without duplicate tables.
    Returns the aggregated, platform-prioritized list of SearchItem results.
    """
    con = console or Console(legacy_windows=False)
    if not managers:
        con.print("[yellow]No active package managers available to search.[/]")
        return []

    con.print(f"\n[bold #00f0ff]⚡ Scanning across {len(managers)} package managers (top 3 per searcher, expandable)...[/]")

    all_items: List[SearchItem] = []
    in_progress = set(managers)
    completed: Dict[str, int] = {}
    start_time = time.time()

    # Sort managers by priority to start highest priority workers first
    ordered_managers = sorted(managers, key=get_manager_weight, reverse=True)

    with Live(
        build_results_table(all_items, in_progress, completed, query),
        console=con,
        refresh_per_second=8,
        transient=True,
    ) as live:
        with ThreadPoolExecutor(max_workers=min(len(ordered_managers), 8)) as executor:
            future_to_manager = {
                executor.submit(
                    execute_manager_search,
                    mpm_exec,
                    mgr,
                    query,
                    timeout_per_manager,
                ): mgr
                for mgr in ordered_managers
            }

            for future in as_completed(future_to_manager):
                mgr = future_to_manager[future]
                in_progress.discard(mgr)

                try:
                    manager_id, results, err = future.result()
                    if results:
                        all_items.extend(results)
                        completed[manager_id] = len(results)
                    else:
                        completed[manager_id] = 0
                except Exception:
                    completed[mgr] = 0

                # Refresh live table with newly arrived results
                live.update(build_results_table(all_items, in_progress, completed, query))

    elapsed = time.time() - start_time
    con.print(
        f"\n[dim]✔ Search completed in {elapsed:.2f}s: "
        f"[bold]{len(all_items)}[/] package(s) found across {len(completed)} manager(s).[/]\n"
    )

    # Final prioritized sort
    sorted_items = sorted(
        all_items,
        key=lambda x: (x.priority, 1 if x.package_id.lower() == query.lower() else 0),
        reverse=True,
    )
    if sorted_items:
        sorted_items[0].is_recommended = True

    return sorted_items
