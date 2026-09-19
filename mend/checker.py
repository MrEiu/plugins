"""
Concurrent Plugin Dependency Health Checker for Kapsel Mend Plugin.
Scans tools.yaml across all plugins concurrently (4-thread worker pool)
to detect missing external tools and generate an actionable diagnostic report.

All comments and docstrings are in English.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
import threading
from typing import Dict, List, Optional, Tuple

from rich.console import Console
from rich.table import Table

from kapsel.core.tools.registry import get_registry, get_all_tools
from kapsel.core.tools.installer import is_tool_installed, resolve_tool_executable, install_tool


@dataclass
class ToolCheckResult:
    plugin: str
    tool_id: str
    tool_name: str
    is_installed: bool
    location: Optional[str]
    description: str
    fix_command: str


def check_single_tool(tool_id: str, tool_def: dict) -> ToolCheckResult:
    """Checks whether a single tool is installed and resolves its location."""
    plugin = tool_def.get("plugin") or tool_def.get("origin", "core")
    name = tool_def.get("name", tool_id)
    desc = tool_def.get("description", "")
    bin_name = tool_def.get("bin", tool_id)

    location = resolve_tool_executable(tool_id)
    installed = location is not None

    fix_cmd = f"kps install {tool_id}"

    return ToolCheckResult(
        plugin=plugin,
        tool_id=tool_id,
        tool_name=name,
        is_installed=installed,
        location=location,
        description=desc,
        fix_command=fix_cmd,
    )


def concurrent_check_all_dependencies(
    console: Optional[Console] = None,
    max_workers: int = 4,
) -> Tuple[List[ToolCheckResult], List[ToolCheckResult]]:
    """
    Concurrently verifies tool dependencies across all Kapsel plugins.
    Returns (all_results, missing_results).
    """
    con = console or Console(legacy_windows=False)
    reg = get_registry()
    tools_dict = reg.collect_all_tools()

    if not tools_dict:
        con.print("[yellow]No tool dependencies registered in Kapsel.[/]")
        return [], []

    con.print(f"\n[bold #00f0ff]🩺 Inspecting {len(tools_dict)} external tool dependencies ({max_workers} Concurrent Threads)...[/]\n")

    results: List[ToolCheckResult] = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_tid = {
            executor.submit(check_single_tool, tid, tdef): tid
            for tid, tdef in tools_dict.items()
        }
        for future in as_completed(future_to_tid):
            try:
                res = future.result()
                results.append(res)
            except Exception:
                pass

    # Sort results by plugin, then by tool_id
    results.sort(key=lambda r: (r.plugin, r.tool_id))
    missing = [r for r in results if not r.is_installed]
    ready = [r for r in results if r.is_installed]

    # Render Rich Diagnostic Matrix Table
    table = Table(
        title="[bold #00f0ff]📋 Kapsel Plugin Tool Dependency Diagnostic Matrix[/]",
        border_style="#0891b2",
        header_style="bold #38bdf8",
        box=None,
    )
    table.add_column("Plugin", style="cyan", width=14)
    table.add_column("Tool", style="bold white", width=18)
    table.add_column("Status", width=14)
    table.add_column("Resolved Location / Fix Recommendation", style="dim")

    current_plugin = ""
    for r in results:
        # Group visually by plugin
        plugin_col = r.plugin if r.plugin != current_plugin else ""
        current_plugin = r.plugin

        if r.is_installed:
            status_str = "[bold #10b981]✔ Ready[/]"
            info_str = f"[dim green]{r.location}[/]"
        else:
            status_str = "[bold #f43f5e]✘ Missing[/]"
            info_str = f"[bold yellow]{r.fix_command}[/]"

        table.add_row(plugin_col, r.tool_name, status_str, info_str)

    con.print(table)

    con.print(
        f"\n[bold white]Health Summary:[/] "
        f"[bold #10b981]{len(ready)} ready[/], "
        f"[bold {'#f43f5e' if missing else '#10b981'}]{len(missing)} missing[/] "
        f"across {len(results)} inspected tools."
    )

    if missing:
        con.print("\n[bold #f59e0b]💡 Missing Dependencies Found![/]")
        con.print("Run '[bold #00f0ff]kps mend fix[/]' to automatically install all missing tools via declarative strategies.\n")
    else:
        con.print("\n[bold #10b981]🎉 All plugin dependencies are satisfied and ready![/]\n")

    return results, missing


def auto_fix_missing_dependencies(
    missing_results: List[ToolCheckResult],
    console: Optional[Console] = None,
) -> int:
    """
    Automatically installs all missing dependencies using Kapsel core declarative installer.
    """
    con = console or Console(legacy_windows=False)
    if not missing_results:
        con.print("[bold #10b981]✔ No missing dependencies to fix.[/]\n")
        return 0

    total = len(missing_results)
    con.print(f"\n[bold #00f0ff]🔧 Auto-installing {total} missing plugin dependencies...[/]\n")

    succeeded = 0
    failed = 0

    for idx, item in enumerate(missing_results, 1):
        con.print(f"[bold #00f0ff]━━━ [{idx}/{total}] Fixing: [white]{item.tool_id}[/] (for plugin '{item.plugin}') ━━━[/]")
        try:
            ok = install_tool(item.tool_id, console=con)
            if ok:
                succeeded += 1
                con.print(f"  [bold #10b981]✔ Successfully installed {item.tool_id}![/]\n")
            else:
                failed += 1
                con.print(f"  [bold #f43f5e]✘ Failed to install {item.tool_id}.[/]\n")
        except Exception as e:
            failed += 1
            con.print(f"  [bold #f43f5e]✘ Error installing {item.tool_id}:[/] {e}\n")

    con.print(
        f"[bold {'#10b981' if failed == 0 else '#f59e0b'}]Mend Fix Complete:[/] "
        f"[white]{succeeded} fixed[/], "
        f"[{'#f43f5e' if failed else 'white'}]{failed} failed[/].\n"
    )
    return 0 if failed == 0 else 1
