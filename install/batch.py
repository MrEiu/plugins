"""
Multi-Package Concurrent & Batch Installer for Kapsel Install Plugin.
Enables parallel installation of multiple packages across system package managers,
rendering real-time task status, summary table, and post-install inspection.

All comments and docstrings are in English.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

try:
    from .inspector import inspect_installed_package, resolve_binary_location
except ImportError:
    from plugins.install.inspector import inspect_installed_package, resolve_binary_location

try:
    from kapsel.core.tools.registry import get_tool
    from kapsel.core.tools.installer import install_tool
except ImportError:
    get_tool = None
    install_tool = None


def run_single_package_install(
    package: str,
    mpm_exec: Optional[List[str]],
    priority_flags: List[str],
    extra_flags: List[str],
    console: Optional[Console] = None,
    custom_paths: Optional[Dict[str, str]] = None,
) -> Tuple[str, int, str, float, str]:
    """
    Executes installation of a single package.
    Returns: (package_name, exit_code, output_text, duration_seconds, manager_label)
    """
    t0 = time.perf_counter()

    # 1. Check declarative tools registry first
    if get_tool and not any(f.startswith("--") for f in extra_flags):
        tool_def = get_tool(package)
        if tool_def:
            ok = install_tool(package, console=None)
            t1 = time.perf_counter()
            origin = tool_def.get("plugin", "declarative")
            return (package, 0 if ok else 1, f"Installed via declarative ({origin})", t1 - t0, origin)

    # 2. Fallback to MPM
    if not mpm_exec:
        t1 = time.perf_counter()
        return (package, 1, "mpm executable not found", t1 - t0, "none")

    cmd = mpm_exec + priority_flags + ["install"] + extra_flags + [package]
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    if custom_paths:
        dirs_to_add: List[str] = []
        for mid, p in custom_paths.items():
            p_path = Path(p)
            d = str(p_path.parent if p_path.is_file() else p_path)
            if d not in dirs_to_add and os.path.isdir(d):
                dirs_to_add.append(d)
            env[f"KAPSEL_MPM_{mid.upper().replace('-', '_')}_PATH"] = str(p_path)
        if dirs_to_add:
            env["PATH"] = os.pathsep.join(dirs_to_add) + os.pathsep + env.get("PATH", "")

    detected_mgr = "mpm"
    for f in priority_flags:
        if f.startswith("--") and len(f) > 2:
            detected_mgr = f[2:]
            break

    try:
        proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
        t1 = time.perf_counter()
        output = (proc.stdout or "") + (proc.stderr or "")
        return (package, proc.returncode, output, t1 - t0, detected_mgr)
    except Exception as e:
        t1 = time.perf_counter()
        return (package, 1, str(e), t1 - t0, detected_mgr)


def install_packages_batch(
    packages: List[str],
    args: List[str],
    plugin: Any,
    console: Optional[Console] = None,
) -> int:
    """
    Installs multiple packages concurrently or sequentially based on options.
    """
    con = console or Console(legacy_windows=False)
    from plugins.install.plugin import _resolve_mpm_executable, MPM_SUPPORTED_SELECTORS

    mpm_exec = _resolve_mpm_executable()
    if not mpm_exec:
        con.print("[bold #f43f5e]Error:[/] [white]meta-package-manager (mpm) is not installed.[/]")
        con.print("[dim]Install it via 'scoop install main/meta-package-manager' or 'brew install meta-package-manager'.[/]\n")
        return 1

    # Extract flags
    is_sequential = any(a in ("-s", "--sequential", "--sync", "--serial") for a in args)
    extra_flags = [
        a for a in args
        if a.startswith("-") and a not in ("-s", "--sequential", "--sync", "--serial", "-c", "--concurrent")
    ]

    active_managers = plugin.get_active_managers() if hasattr(plugin, "get_active_managers") else []
    priority_flags = [f"--{m}" for m in active_managers if m in MPM_SUPPORTED_SELECTORS]
    conf = plugin.load_config() if hasattr(plugin, "load_config") else {}
    custom_paths = conf.get("custom_paths", {})

    total = len(packages)
    mode_label = "Sequential" if is_sequential else "Concurrent"
    con.print(f"\n[bold #00f0ff]⚡ [Install Batch][/] [cyan]{mode_label} Installer[/] [dim]({total} packages scheduled)[/]")
    for i, p in enumerate(packages, 1):
        con.print(f"  [dim]• [{i}/{total}][/] [white]{p}[/]")
    con.print("")

    results: List[Tuple[str, int, str, float, str]] = []
    t_start = time.perf_counter()

    if is_sequential:
        for idx, pkg in enumerate(packages, 1):
            con.print(f"[dim]⚡ [{idx}/{total}][/] [cyan]Installing [bold white]{pkg}[/]...[/]")
            res = run_single_package_install(
                package=pkg,
                mpm_exec=mpm_exec,
                priority_flags=priority_flags,
                extra_flags=extra_flags,
                console=con,
                custom_paths=custom_paths,
            )
            results.append(res)
            _, code, _, dur, mgr = res
            status_tag = "[bold #10b981]✔ SUCCESS[/]" if code == 0 else f"[bold #f43f5e]✖ FAILED ({code})[/]"
            con.print(f"    └─ {status_tag} [dim]via {mgr} ({dur:.1f}s)[/]\n")
    else:
        # Concurrent mode: ThreadPoolExecutor
        workers = min(total, 4)
        con.print(f"[dim]⚡ Dispatching parallel installation threads (max workers: {workers})...[/]\n")

        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_pkg = {
                executor.submit(
                    run_single_package_install,
                    pkg,
                    mpm_exec,
                    priority_flags,
                    extra_flags,
                    con,
                    custom_paths,
                ): pkg
                for pkg in packages
            }

            for future in as_completed(future_to_pkg):
                pkg = future_to_pkg[future]
                try:
                    res = future.result()
                    results.append(res)
                    _, code, _, dur, mgr = res
                    if code == 0:
                        con.print(f"  [bold #10b981]✔[/] [white]{pkg}[/] [dim]installed via {mgr} ({dur:.1f}s)[/]")
                    else:
                        con.print(f"  [bold #f43f5e]✖[/] [white]{pkg}[/] [bold #f43f5e]failed[/] [dim]({dur:.1f}s)[/]")
                except Exception as exc:
                    results.append((pkg, 1, str(exc), 0.0, "error"))
                    con.print(f"  [bold #f43f5e]✖[/] [white]{pkg}[/] [dim]errored: {exc}[/]")

    total_duration = time.perf_counter() - t_start

    # Render summary table
    table = Table(title="📦 Batch Installation Summary", border_style="#00f0ff")
    table.add_column("Package", style="bold white")
    table.add_column("Manager", style="cyan")
    table.add_column("Status", justify="center")
    table.add_column("Duration", justify="right", style="dim")
    table.add_column("Location", style="dim")

    success_count = 0
    for pkg, code, out, dur, mgr in results:
        bin_loc = resolve_binary_location(pkg)
        loc_str = str(bin_loc) if bin_loc else "[dim](not in PATH)[/]"
        if code == 0:
            success_count += 1
            status_badge = "[bold #10b981]✔ OK[/]"
        else:
            status_badge = f"[bold #f43f5e]✖ ERR ({code})[/]"
        table.add_row(pkg, mgr, status_badge, f"{dur:.1f}s", loc_str)

    con.print("")
    con.print(table)
    con.print(
        f"[dim]Finished in {total_duration:.1f}s · {success_count}/{total} package(s) installed successfully.[/]\n"
    )

    # Inspect successfully installed packages
    for pkg, code, _, _, mgr in results:
        if code == 0:
            inspect_installed_package(pkg, manager=mgr, console=con)

    return 0 if success_count == total else 1
