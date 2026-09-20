"""
Interactive Package Confirmation Selector for Kapsel Install Plugin.
Presents a unified, grouped selection menu (top 3 packages per manager by default),
with interactive expansion/collapsing, arrow-key navigation, and secondary confirmation.
Supports live streaming search where results appear dynamically as found,
allowing immediate selection without waiting for all managers to complete.

All comments and docstrings are in English.
"""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import sys
import threading
import time
from typing import Any, Dict, List, Optional, Set, Union

from rich.console import Console

from .streaming_search import SearchItem, get_manager_weight, execute_manager_search


@dataclass
class ItemRow:
    item: SearchItem
    manager: str


@dataclass
class ToggleRow:
    manager: str
    is_expanded: bool
    hidden_count: int


def search_and_select_interactive(
    mpm_exec: List[str],
    managers: List[str],
    query: str,
    console: Optional[Console] = None,
    timeout_per_manager: int = 35,
) -> Optional[SearchItem]:
    """
    Initiates concurrent multi-manager search and immediately opens the interactive UI.
    Results stream into the menu as soon as each manager finishes, allowing the user
    to immediately select and install without waiting for all managers to complete.
    """
    con = console or Console(legacy_windows=False)
    if not managers:
        con.print("[yellow]No active package managers available to search.[/]")
        return None

    if not sys.stdin.isatty():
        # Fallback to streaming search in non-interactive / piped environments
        from .streaming_search import concurrent_streaming_search
        results = concurrent_streaming_search(mpm_exec, managers, query, con)
        if not results:
            return None
        return results[0]

    try:
        from prompt_toolkit.application import Application
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.layout.containers import HSplit, Window
        from prompt_toolkit.layout.controls import FormattedTextControl
        from prompt_toolkit.layout.layout import Layout
        from prompt_toolkit.styles import Style

        lock = threading.Lock()
        is_running = True
        app: Optional[Application] = None

        grouped: Dict[str, List[SearchItem]] = {}
        in_progress: Set[str] = set(managers)
        completed: Dict[str, int] = {}
        expanded_managers: Set[str] = set()
        visible_rows: List[Union[ItemRow, ToggleRow]] = []
        selected_idx = 0
        result: List[Optional[SearchItem]] = [None]
        has_found_recommended = False

        ordered_managers = sorted(managers, key=get_manager_weight, reverse=True)

        def rebuild_visible_rows():
            nonlocal visible_rows, has_found_recommended
            visible_rows = []
            has_found_recommended = False

            for mgr in ordered_managers:
                if mgr not in grouped:
                    continue
                mgr_items = grouped[mgr]
                # Sort exact match and priority first
                mgr_items = sorted(
                    mgr_items,
                    key=lambda x: (1 if x.package_id.lower() == query.lower() else 0, x.priority),
                    reverse=True,
                )

                if not has_found_recommended and mgr_items:
                    top_it = mgr_items[0]
                    if top_it.package_id.lower() == query.lower() or top_it.priority >= 90:
                        top_it.is_recommended = True
                        has_found_recommended = True

                if mgr in expanded_managers:
                    for it in mgr_items:
                        visible_rows.append(ItemRow(item=it, manager=mgr))
                    if len(mgr_items) > 3:
                        visible_rows.append(ToggleRow(manager=mgr, is_expanded=True, hidden_count=0))
                else:
                    for it in mgr_items[:3]:
                        visible_rows.append(ItemRow(item=it, manager=mgr))
                    if len(mgr_items) > 3:
                        visible_rows.append(ToggleRow(manager=mgr, is_expanded=False, hidden_count=len(mgr_items) - 3))

        def notify_redraw():
            if app and is_running:
                try:
                    loop = getattr(app, "loop", None)
                    if loop and loop.is_running():
                        loop.call_soon_threadsafe(app.invalidate)
                    else:
                        app.invalidate()
                except Exception:
                    pass

        # Background worker for concurrent manager search
        def _search_worker(mgr_id: str):
            nonlocal selected_idx
            try:
                manager_id, items, err = execute_manager_search(mpm_exec, mgr_id, query, timeout_per_manager)
            except Exception:
                manager_id, items, err = mgr_id, [], "error"

            with lock:
                in_progress.discard(manager_id)
                completed[manager_id] = len(items)
                if items:
                    grouped[manager_id] = items
                rebuild_visible_rows()
                if visible_rows and selected_idx >= len(visible_rows):
                    selected_idx = len(visible_rows) - 1

            notify_redraw()

        executor = ThreadPoolExecutor(max_workers=min(len(ordered_managers), 8))
        for mgr in ordered_managers:
            executor.submit(_search_worker, mgr)

        def get_menu_text():
            with lock:
                lines = []
                # Header with live streaming status
                if in_progress:
                    scanning_mgrs = ", ".join(sorted(in_progress))
                    lines.append(("class:scanning", f"\n  ⚡ Searching registries ({len(in_progress)} scanning: {scanning_mgrs})...\n"))
                    lines.append(("class:hint", "  💡 Select any result immediately with [Enter] without waiting for scan to finish.\n\n"))
                else:
                    total_found = sum(len(v) for v in grouped.values())
                    lines.append(("class:done", f"\n  ✔ All {len(completed)} managers scanned (Found {total_found} packages total).\n\n"))

                if not visible_rows:
                    if in_progress:
                        lines.append(("class:dim", "   Scanning package registries in background... Results will appear here instantly.\n"))
                    else:
                        lines.append(("class:warn", f"   No packages found matching '{query}'.\n"))
                    return lines

                current_mgr = None
                for i, row in enumerate(visible_rows):
                    is_cur = (i == selected_idx)
                    cursor = " ❯ " if is_cur else "   "

                    if row.manager != current_mgr:
                        current_mgr = row.manager
                        total_count = len(grouped.get(current_mgr, []))
                        expand_status = "(expanded)" if current_mgr in expanded_managers else f"({min(3, total_count)}/{total_count} shown)"
                        header_line = f"  ╭─ 📦 [{current_mgr.upper()}] {expand_status} ──────────────────────────────────────\n"
                        lines.append(("class:header", header_line))

                    if isinstance(row, ItemRow):
                        it = row.item
                        rec_tag = " [★ BEST]" if it.is_recommended else ""
                        warn_tag = " (⚠ Python Package)" if (it.manager == "pip" and not it.is_recommended) else ""
                        ver = f"v{it.version}" if it.version else ""
                        desc = f" - {it.description[:42]}..." if it.description else ""
                        row_str = f"{cursor}{it.package_id:<26} {ver:<10}{rec_tag}{warn_tag}{desc}\n"
                        style_class = "class:selected" if is_cur else "class:normal"
                        lines.append((style_class, row_str))

                    elif isinstance(row, ToggleRow):
                        if row.is_expanded:
                            toggle_str = f"{cursor} ▾ [Collapse {row.manager} to top 3]\n"
                        else:
                            toggle_str = f"{cursor} ▸ [+ {row.hidden_count} more from {row.manager}] (Press Enter or 'e' to expand)\n"
                        style_class = "class:selected_toggle" if is_cur else "class:toggle"
                        lines.append((style_class, toggle_str))

                lines.append(("\nclass:help", "  [↑/↓] Navigate  |  [Enter] Confirm/Expand  |  [e] Toggle Expand  |  [Esc/q] Cancel\n"))
                return lines

        kb = KeyBindings()

        @kb.add("up")
        def _on_up(event):
            nonlocal selected_idx
            with lock:
                if visible_rows:
                    selected_idx = (selected_idx - 1) % len(visible_rows)
            notify_redraw()

        @kb.add("down")
        def _on_down(event):
            nonlocal selected_idx
            with lock:
                if visible_rows:
                    selected_idx = (selected_idx + 1) % len(visible_rows)
            notify_redraw()

        @kb.add("enter")
        def _on_enter(event):
            nonlocal selected_idx, is_running
            with lock:
                if not visible_rows:
                    return
                row = visible_rows[selected_idx]
                if isinstance(row, ToggleRow):
                    if row.manager in expanded_managers:
                        expanded_managers.remove(row.manager)
                    else:
                        expanded_managers.add(row.manager)
                    rebuild_visible_rows()
                    selected_idx = min(selected_idx, len(visible_rows) - 1)
                    notify_redraw()
                    return
                elif isinstance(row, ItemRow):
                    result[0] = row.item
                    is_running = False
                    event.app.exit()

        @kb.add("e")
        def _on_expand(event):
            nonlocal selected_idx
            with lock:
                if not visible_rows:
                    return
                cur_row = visible_rows[selected_idx]
                mgr = cur_row.manager
                if mgr in expanded_managers:
                    expanded_managers.remove(mgr)
                else:
                    expanded_managers.add(mgr)
                rebuild_visible_rows()
                selected_idx = min(selected_idx, len(visible_rows) - 1)
            notify_redraw()

        @kb.add("escape")
        @kb.add("q")
        def _on_cancel(event):
            nonlocal is_running
            is_running = False
            result[0] = None
            event.app.exit()

        style = Style.from_dict({
            "scanning": "bold fg:#00f0ff",
            "done": "bold fg:#10b981",
            "hint": "dim italic fg:#38bdf8",
            "dim": "dim fg:#64748b",
            "warn": "italic fg:#f59e0b",
            "header": "bold fg:#38bdf8",
            "selected": "bold fg:#00f0ff bg:#1e293b",
            "normal": "fg:#e2e8f0",
            "selected_toggle": "bold fg:#f59e0b bg:#1e293b",
            "toggle": "italic fg:#f59e0b",
            "help": "dim fg:#94a3b8",
        })

        layout = Layout(HSplit([Window(content=FormattedTextControl(get_menu_text))]))
        app = Application(layout=layout, key_bindings=kb, style=style, full_screen=False)
        app.run()

        # Stop worker dispatch
        is_running = False
        executor.shutdown(wait=False)

        return result[0]

    except Exception:
        # Fallback to streaming search and numeric menu
        from .streaming_search import concurrent_streaming_search
        results = concurrent_streaming_search(mpm_exec, managers, query, con)
        return select_package_interactive(results, con)


def select_package_interactive(
    candidates: List[SearchItem],
    console: Optional[Console] = None,
) -> Optional[SearchItem]:
    """
    Presents an interactive menu to let the user select and confirm the exact package
    from an already fetched list of candidate SearchItems.
    """
    con = console or Console(legacy_windows=False)

    if not candidates:
        con.print("[yellow]No packages available to select.[/]")
        return None

    # Group items by manager
    grouped: Dict[str, List[SearchItem]] = {}
    for item in candidates:
        grouped.setdefault(item.manager, []).append(item)

    # Order managers by platform priority weight
    ordered_managers = sorted(grouped.keys(), key=get_manager_weight, reverse=True)

    if not sys.stdin.isatty():
        return _numeric_selection_fallback(ordered_managers, grouped, con)

    try:
        from prompt_toolkit.application import Application
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.layout.containers import HSplit, Window
        from prompt_toolkit.layout.controls import FormattedTextControl
        from prompt_toolkit.layout.layout import Layout
        from prompt_toolkit.styles import Style

        expanded_managers: Set[str] = set()
        visible_rows: List[Union[ItemRow, ToggleRow]] = []
        selected_idx = 0
        result: List[Optional[SearchItem]] = [None]

        def rebuild_visible_rows():
            nonlocal visible_rows
            visible_rows = []
            for mgr in ordered_managers:
                mgr_items = grouped[mgr]
                if mgr in expanded_managers:
                    for it in mgr_items:
                        visible_rows.append(ItemRow(item=it, manager=mgr))
                    if len(mgr_items) > 3:
                        visible_rows.append(ToggleRow(manager=mgr, is_expanded=True, hidden_count=0))
                else:
                    for it in mgr_items[:3]:
                        visible_rows.append(ItemRow(item=it, manager=mgr))
                    if len(mgr_items) > 3:
                        visible_rows.append(ToggleRow(manager=mgr, is_expanded=False, hidden_count=len(mgr_items) - 3))

        rebuild_visible_rows()

        def get_menu_text():
            lines = []
            current_mgr = None

            for i, row in enumerate(visible_rows):
                is_cur = (i == selected_idx)
                cursor = " ❯ " if is_cur else "   "

                if row.manager != current_mgr:
                    current_mgr = row.manager
                    total_count = len(grouped[current_mgr])
                    expand_status = "(expanded)" if current_mgr in expanded_managers else f"({min(3, total_count)}/{total_count} shown)"
                    header_line = f"\n  ╭─ 📦 [{current_mgr.upper()}] {expand_status} ──────────────────────────────────────\n"
                    lines.append(("class:header", header_line))

                if isinstance(row, ItemRow):
                    it = row.item
                    rec_tag = " [★ BEST]" if it.is_recommended else ""
                    warn_tag = " (⚠ Python Package)" if (it.manager == "pip" and not it.is_recommended) else ""
                    ver = f"v{it.version}" if it.version else ""
                    desc = f" - {it.description[:42]}..." if it.description else ""
                    row_str = f"{cursor}{it.package_id:<26} {ver:<10}{rec_tag}{warn_tag}{desc}\n"
                    style_class = "class:selected" if is_cur else "class:normal"
                    lines.append((style_class, row_str))

                elif isinstance(row, ToggleRow):
                    if row.is_expanded:
                        toggle_str = f"{cursor} ▾ [Collapse {row.manager} to top 3]\n"
                    else:
                        toggle_str = f"{cursor} ▸ [+ {row.hidden_count} more from {row.manager}] (Press Enter or 'e' to expand)\n"
                    style_class = "class:selected_toggle" if is_cur else "class:toggle"
                    lines.append((style_class, toggle_str))

            lines.append(("\nclass:help", "  [↑/↓] Navigate  |  [Enter] Confirm/Expand  |  [e] Toggle Expand  |  [Esc/q] Cancel\n"))
            return lines

        kb = KeyBindings()

        @kb.add("up")
        def _on_up(event):
            nonlocal selected_idx
            if visible_rows:
                selected_idx = (selected_idx - 1) % len(visible_rows)

        @kb.add("down")
        def _on_down(event):
            nonlocal selected_idx
            if visible_rows:
                selected_idx = (selected_idx + 1) % len(visible_rows)

        @kb.add("enter")
        def _on_enter(event):
            nonlocal selected_idx
            if not visible_rows:
                event.app.exit()
                return

            row = visible_rows[selected_idx]
            if isinstance(row, ToggleRow):
                if row.manager in expanded_managers:
                    expanded_managers.remove(row.manager)
                else:
                    expanded_managers.add(row.manager)
                rebuild_visible_rows()
                selected_idx = min(selected_idx, len(visible_rows) - 1)
            elif isinstance(row, ItemRow):
                result[0] = row.item
                event.app.exit()

        @kb.add("e")
        def _on_expand(event):
            nonlocal selected_idx
            if not visible_rows:
                return
            cur_row = visible_rows[selected_idx]
            mgr = cur_row.manager
            if mgr in expanded_managers:
                expanded_managers.remove(mgr)
            else:
                expanded_managers.add(mgr)
            rebuild_visible_rows()
            selected_idx = min(selected_idx, len(visible_rows) - 1)

        @kb.add("escape")
        @kb.add("q")
        def _on_cancel(event):
            result[0] = None
            event.app.exit()

        style = Style.from_dict({
            "header": "bold fg:#38bdf8",
            "selected": "bold fg:#00f0ff bg:#1e293b",
            "normal": "fg:#e2e8f0",
            "selected_toggle": "bold fg:#f59e0b bg:#1e293b",
            "toggle": "italic fg:#f59e0b",
            "help": "dim fg:#94a3b8",
        })

        layout = Layout(HSplit([Window(content=FormattedTextControl(get_menu_text))]))
        app = Application(layout=layout, key_bindings=kb, style=style, full_screen=False)
        app.run()

        return result[0]

    except Exception:
        return _numeric_selection_fallback(ordered_managers, grouped, con)


def _numeric_selection_fallback(
    first_arg: Any,
    second_arg: Any = None,
    third_arg: Optional[Console] = None,
) -> Optional[SearchItem]:
    """
    Fallback interactive prompt using plain terminal input.
    Accepts either (candidates: List[SearchItem], con: Optional[Console])
    or (ordered_managers: List[str], grouped: Dict[str, List[SearchItem]], con: Console).
    """
    if isinstance(first_arg, list) and first_arg and isinstance(first_arg[0], SearchItem):
        candidates: List[SearchItem] = first_arg
        con: Console = second_arg or Console(legacy_windows=False)
        grouped: Dict[str, List[SearchItem]] = {}
        for item in candidates:
            grouped.setdefault(item.manager, []).append(item)
        ordered_managers = sorted(grouped.keys(), key=get_manager_weight, reverse=True)
    else:
        ordered_managers = first_arg or []
        grouped = second_arg or {}
        con = third_arg or Console(legacy_windows=False)

    flat_indexed: List[SearchItem] = []
    idx = 1

    con.print("\n[bold #00f0ff]📦 Available Package Candidates (Top 3 per manager):[/]")
    for mgr in ordered_managers:
        items = grouped.get(mgr, [])
        con.print(f"  [bold cyan][{mgr.upper()}][/] ({len(items)} found):")
        for it in items[:3]:
            rec_tag = " [bold #10b981]★ BEST[/]" if it.is_recommended else ""
            warn_tag = " [bold yellow](⚠ Python Package)[/]" if (it.manager == "pip" and not it.is_recommended) else ""
            ver_str = f"v{it.version}" if it.version else ""
            con.print(f"    [bold #38bdf8][{idx}][/] {it.package_id} {ver_str}{rec_tag}{warn_tag}")
            if it.description:
                con.print(f"        [dim]{it.description[:55]}[/]")
            flat_indexed.append(it)
            idx += 1
        if len(items) > 3:
            con.print(f"    [dim italic]... and {len(items) - 3} more from {mgr}[/]")

    con.print("")
    try:
        choice = input(f"Enter selection [1-{len(flat_indexed)}] or 'q' to cancel: ").strip()
        if choice.lower() in ("q", "quit", "exit", ""):
            return None
        val = int(choice)
        if 1 <= val <= len(flat_indexed):
            return flat_indexed[val - 1]
    except Exception:
        pass

    return None
