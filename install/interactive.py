"""
Interactive Package Confirmation Selector for Kapsel Install Plugin.
Renders a unified, complete framed rounded card (Unified Framed Panel)
with strict column alignment, top-3 candidates per search provider,
and dynamic live expansion/collapsing.

All comments and docstrings are in English.
"""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import re
import shutil
import sys
import threading
from typing import Any, Dict, List, Optional, Set, Tuple, Union

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


def parse_semver(ver_str: Optional[str]) -> Tuple[int, ...]:
    """Parses version string into numeric tuple for semver ranking."""
    if not ver_str:
        return (0, 0, 0)
    nums = [int(n) for n in re.findall(r"\d+", str(ver_str))]
    return tuple(nums[:3]) if nums else (0, 0, 0)


def rank_manager_candidates(items: List[SearchItem], query: str) -> List[SearchItem]:
    """
    Ranks candidates within a manager:
    Prioritizes exact name matches, modern semver (>= 1.0.0), and token matches over stale 0.x crates.
    """
    q = query.lower()

    def sort_key(it: SearchItem):
        pid = it.package_id.lower()
        exact = (pid == q)
        token_match = (f"-{q}" in pid) or (f"{q}-" in pid) or pid.startswith(q) or pid.endswith(q)
        ver = parse_semver(it.version)
        is_modern = 1 if ver >= (1, 0, 0) else 0

        # Tier 3: exact match with modern version (>= 1.0.0)
        # Tier 2: token/prefix/suffix match with modern version (e.g. du-dust v1.2.6)
        # Tier 1: exact match but ancient version (< 1.0.0)
        # Tier 0: partial/loose match
        if exact and is_modern:
            tier = 3
        elif token_match and is_modern:
            tier = 2
        elif exact:
            tier = 1
        else:
            tier = 0

        len_diff = abs(len(pid) - len(q))

        return (
            1 if it.is_recommended else 0,
            tier,
            -len_diff,
            ver,
            it.priority,
        )

    return sorted(items, key=sort_key, reverse=True)


def build_card_title_formatted_text(
    query: str,
    visible_rows: List[Union[ItemRow, ToggleRow]],
    in_progress: Optional[Set[str]] = None,
    completed: Optional[Dict[str, int]] = None,
) -> List[Tuple[str, str]]:
    """Builds the adaptive title bar for the package search card."""
    if in_progress:
        status_text = f"Searching ({len(in_progress)} active)"
    elif completed is not None:
        status_text = f"Scan complete ({sum(completed.values())} found)"
    else:
        status_text = f"Found {len(visible_rows)} candidates"
    return [
        ("class:border", " 📦 Package Search: "),
        ("class:mgr_header", f"'{query}'"),
        ("class:help", f" [{status_text}] "),
    ]


def build_card_body_formatted_text(
    query: str,
    ordered_managers: List[str],
    grouped: Dict[str, List[SearchItem]],
    expanded_managers: Set[str],
    visible_rows: List[Union[ItemRow, ToggleRow]],
    selected_idx: int,
    in_progress: Optional[Set[str]] = None,
    completed: Optional[Dict[str, int]] = None,
    row_to_line_map: Optional[Dict[int, int]] = None,
) -> List[Tuple[str, str]]:
    """
    Renders inner content lines for the card body.
    Columns adapt dynamically to the terminal width to prevent text overflow.
    No outer border characters are emitted here; prompt_toolkit's layout container
    draws the outer frame cleanly in dedicated columns.
    """
    lines: List[Tuple[str, str]] = []
    term_cols = shutil.get_terminal_size((80, 24)).columns
    avail_w = max(36, term_cols - 4)

    if row_to_line_map is not None:
        row_to_line_map.clear()

    current_line = 0

    if not visible_rows:
        if in_progress:
            scanning_names = ", ".join(sorted(in_progress))
            lines.append(("class:scanning", f"  Scanning registries in background: {scanning_names}...\n"))
        else:
            lines.append(("class:warn", f"  No packages found matching '{query}' across active managers.\n"))
        return lines

    cursor_w = 3
    pkg_col_w = min(24, max(14, avail_w // 4))
    ver_col_w = 9
    badge_col_w = 10
    rem_desc_w = max(8, avail_w - (cursor_w + pkg_col_w + ver_col_w + badge_col_w + 4))

    current_mgr = None
    first_section = True

    for i, row in enumerate(visible_rows):
        is_cur = (i == selected_idx)
        cursor = " ❯ " if is_cur else "   "

        if row.manager != current_mgr:
            if not first_section:
                lines.append(("", "\n"))
                current_line += 1
            first_section = False

            current_mgr = row.manager
            total_in_mgr = len(grouped.get(current_mgr, []))
            expand_label = "(expanded)" if current_mgr in expanded_managers else f"({min(3, total_in_mgr)}/{total_in_mgr} shown)"
            lines.append(("class:mgr_header", f"  ● [{current_mgr.upper()}] {expand_label}\n"))
            current_line += 1

        if row_to_line_map is not None:
            row_to_line_map[i] = current_line

        if isinstance(row, ItemRow):
            it = row.item
            rec_tag = "[★ BEST]" if it.is_recommended else ""
            warn_tag = "(⚠ Python)" if (it.manager == "pip" and not it.is_recommended) else ""
            badge_str = rec_tag or warn_tag
            ver_str = f"v{it.version}" if it.version else ""

            pkg_text = f"{it.package_id:<{pkg_col_w}}"[:pkg_col_w]
            ver_text = f"{ver_str:<{ver_col_w}}"[:ver_col_w]
            badge_text = f"{badge_str:<{badge_col_w}}"[:badge_col_w]

            raw_desc = (it.description or "").strip()
            if len(raw_desc) > rem_desc_w:
                desc_text = raw_desc[: max(0, rem_desc_w - 3)] + "..."
            else:
                desc_text = raw_desc

            row_style = "class:selected" if is_cur else "class:normal"
            lines.append((row_style, f"{cursor}{pkg_text}  {ver_text}  {badge_text}  {desc_text}\n"))
            current_line += 1

        elif isinstance(row, ToggleRow):
            if row.is_expanded:
                tog_text = f"▾ [Collapse {row.manager} to top 3]"
            else:
                tog_text = f"▸ [+ {row.hidden_count} more from {row.manager}] (Press Enter or 'e' to expand)"

            tog_style = "class:selected_toggle" if is_cur else "class:toggle"
            lines.append((tog_style, f"{cursor}{tog_text}\n"))
            current_line += 1

    return lines


def build_card_formatted_text(
    query: str,
    ordered_managers: List[str],
    grouped: Dict[str, List[SearchItem]],
    expanded_managers: Set[str],
    visible_rows: List[Union[ItemRow, ToggleRow]],
    selected_idx: int,
    in_progress: Optional[Set[str]] = None,
    completed: Optional[Dict[str, int]] = None,
) -> List[Tuple[str, str]]:
    """Legacy helper for backwards compatibility."""
    return build_card_body_formatted_text(
        query=query,
        ordered_managers=ordered_managers,
        grouped=grouped,
        expanded_managers=expanded_managers,
        visible_rows=visible_rows,
        selected_idx=selected_idx,
        in_progress=in_progress,
        completed=completed,
    )


def create_adaptive_card_layout(
    get_title_func: Any,
    get_body_func: Any,
    get_cursor_func: Optional[Any] = None,
) -> Any:
    """
    Creates an adaptive rounded card layout with guaranteed closed borders.
    Top, bottom, and side borders are rendered in isolated columns by prompt_toolkit,
    preventing any text wrapping or border misalignment.
    """
    from prompt_toolkit.layout.containers import HSplit, VSplit, Window
    from prompt_toolkit.layout.controls import FormattedTextControl
    from prompt_toolkit.layout.dimension import Dimension
    from prompt_toolkit.layout.layout import Layout

    top_bar = VSplit([
        Window(width=1, height=1, char="╭", style="class:border"),
        Window(width=2, height=1, char="─", style="class:border"),
        Window(content=FormattedTextControl(get_title_func), dont_extend_width=True),
        Window(char="─", height=1, style="class:border"),
        Window(width=1, height=1, char="╮", style="class:border"),
    ], height=1)

    term_rows = shutil.get_terminal_size((80, 24)).lines
    max_body_h = max(6, term_rows - 6)

    body_window = Window(
        content=FormattedTextControl(get_body_func, get_cursor_position=get_cursor_func),
        wrap_lines=False,
        height=Dimension(min=3, max=max_body_h),
    )

    mid_bar = VSplit([
        Window(width=1, char="│", style="class:border"),
        body_window,
        Window(width=1, char="│", style="class:border"),
    ])

    bot_bar = VSplit([
        Window(width=1, height=1, char="╰", style="class:border"),
        Window(char="─", height=1, style="class:border"),
        Window(width=1, height=1, char="╯", style="class:border"),
    ], height=1)

    help_bar = Window(
        content=FormattedTextControl(lambda: [
            ("class:help", "  [↑/↓] Navigate  |  [Enter] Confirm/Expand  |  [e] Toggle Expand  |  [Esc/q] Cancel")
        ]),
        height=1,
        style="class:help",
    )

    return Layout(HSplit([top_bar, mid_bar, bot_bar, help_bar]))


def search_and_select_interactive(
    mpm_exec: List[str],
    managers: List[str],
    query: str,
    console: Optional[Console] = None,
    timeout_per_manager: int = 35,
) -> Optional[SearchItem]:
    """
    Initiates concurrent multi-manager search and immediately renders the unified card panel.
    Results stream into the card as soon as each manager finishes, allowing immediate selection.
    """
    con = console or Console(legacy_windows=False)
    if not managers:
        con.print("[yellow]No active package managers available to search.[/]")
        return None

    if not sys.stdin.isatty():
        from .streaming_search import concurrent_streaming_search
        results = concurrent_streaming_search(mpm_exec, managers, query, con)
        return results[0] if results else None

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
                mgr_items = rank_manager_candidates(grouped[mgr], query)

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

        row_to_line: Dict[int, int] = {}

        def get_title_text():
            with lock:
                return build_card_title_formatted_text(
                    query=query,
                    visible_rows=visible_rows,
                    in_progress=in_progress,
                    completed=completed,
                )

        def get_body_text():
            with lock:
                return build_card_body_formatted_text(
                    query=query,
                    ordered_managers=ordered_managers,
                    grouped=grouped,
                    expanded_managers=expanded_managers,
                    visible_rows=visible_rows,
                    selected_idx=selected_idx,
                    in_progress=in_progress,
                    completed=completed,
                    row_to_line_map=row_to_line,
                )

        def get_cursor_pos():
            from prompt_toolkit.data_structures import Point
            with lock:
                y = row_to_line.get(selected_idx, 0)
                return Point(x=1, y=y)

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
            "border": "fg:#38bdf8",
            "mgr_header": "bold fg:#00f0ff",
            "selected": "bold fg:#00f0ff bg:#1e293b",
            "normal": "fg:#f1f5f9",
            "selected_toggle": "bold fg:#f59e0b bg:#1e293b",
            "toggle": "italic fg:#f59e0b",
            "scanning": "bold fg:#00f0ff",
            "warn": "italic fg:#f59e0b",
            "help": "dim fg:#94a3b8",
        })

        layout = create_adaptive_card_layout(get_title_text, get_body_text, get_cursor_pos)
        app = Application(layout=layout, key_bindings=kb, style=style, full_screen=False)
        app.run()

        is_running = False
        executor.shutdown(wait=False)

        return result[0]

    except Exception:
        from .streaming_search import concurrent_streaming_search
        results = concurrent_streaming_search(mpm_exec, managers, query, con)
        return select_package_interactive(results, con)


def select_package_interactive(
    candidates: List[SearchItem],
    console: Optional[Console] = None,
) -> Optional[SearchItem]:
    """
    Presents the unified card panel to let the user select and confirm a package
    from an already fetched list of candidate SearchItems.
    """
    con = console or Console(legacy_windows=False)
    if not candidates:
        con.print("[yellow]No packages available to select.[/]")
        return None

    grouped: Dict[str, List[SearchItem]] = {}
    for item in candidates:
        grouped.setdefault(item.manager, []).append(item)

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
        query = candidates[0].package_id if candidates else "package"

        def rebuild_visible_rows():
            nonlocal visible_rows
            visible_rows = []
            for mgr in ordered_managers:
                mgr_items = rank_manager_candidates(grouped[mgr], query)
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

        row_to_line: Dict[int, int] = {}

        def get_title_text():
            return build_card_title_formatted_text(
                query=query,
                visible_rows=visible_rows,
            )

        def get_body_text():
            return build_card_body_formatted_text(
                query=query,
                ordered_managers=ordered_managers,
                grouped=grouped,
                expanded_managers=expanded_managers,
                visible_rows=visible_rows,
                selected_idx=selected_idx,
                row_to_line_map=row_to_line,
            )

        def get_cursor_pos():
            from prompt_toolkit.data_structures import Point
            y = row_to_line.get(selected_idx, 0)
            return Point(x=1, y=y)

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
            "border": "fg:#38bdf8",
            "mgr_header": "bold fg:#00f0ff",
            "selected": "bold fg:#00f0ff bg:#1e293b",
            "normal": "fg:#f1f5f9",
            "selected_toggle": "bold fg:#f59e0b bg:#1e293b",
            "toggle": "italic fg:#f59e0b",
            "warn": "italic fg:#f59e0b",
            "help": "dim fg:#94a3b8",
        })

        layout = create_adaptive_card_layout(get_title_text, get_body_text, get_cursor_pos)
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
    """Fallback interactive prompt using plain terminal input."""
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
