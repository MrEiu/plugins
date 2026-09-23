"""
Interactive Priority & Status Adjustment Interface for Package Managers.
Provides a modern TUI to reorder managers via:
1. Direction keys (↑/↓ with Space to grab/drop or direct move).
2. Direct numeric ranking (1-9 to jump to specific rank).
3. Enable / Disable toggle (e/d to toggle manager state).

All comments and docstrings are in English.
"""

from pathlib import Path
import shutil
import sys
from typing import Any, Dict, List, Optional, Tuple

from rich.console import Console

try:
    from .plugin import MANAGER_BINARIES, _get_current_platform_key
except ImportError:
    from plugins.install.plugin import MANAGER_BINARIES, _get_current_platform_key


def _get_manager_info(mgr: str, custom_paths: Dict[str, str]) -> Tuple[str, bool]:
    """Returns a display string and presence boolean for the given manager."""
    if mgr in custom_paths:
        cp = Path(custom_paths[mgr])
        if cp.exists():
            return f"(custom) {cp.name}", True
        return f"missing: {cp}", False

    bins = MANAGER_BINARIES.get(mgr, (mgr,))
    found = next((shutil.which(b) for b in bins if shutil.which(b)), None)
    if found:
        return Path(found).name, True
    return "not in PATH", False


def run_order_interactive(plugin_instance: Any, con: Optional[Console] = None) -> int:
    """
    Launches an interactive TUI for package manager priority ordering and status toggling.
    Saves the updated configuration to disk upon completion.
    """
    console = con or Console(legacy_windows=False)
    conf = plugin_instance.load_config()
    plat = conf.get("platform", _get_current_platform_key())
    custom_paths = conf.get("custom_paths", {})

    active_managers: List[str] = list(conf.get("managers", []))
    disabled_managers: List[str] = list(conf.get("disabled", []))

    if not active_managers and not disabled_managers:
        console.print("[bold #f59e0b]No package managers configured.[/]")
        return 0

    try:
        from prompt_toolkit.application import Application
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.layout.containers import HSplit, VSplit, Window
        from prompt_toolkit.layout.controls import FormattedTextControl
        from prompt_toolkit.layout.layout import Layout
        from prompt_toolkit.styles import Style
    except ImportError:
        console.print("[dim]prompt_toolkit not available, falling back to static display.[/]")
        return plugin_instance._show_order(console)

    selected_idx = 0
    is_moving = False
    status_msg = ""

    def get_all_rows() -> List[Tuple[str, bool]]:
        """Returns list of (manager_id, is_active)."""
        rows: List[Tuple[str, bool]] = []
        for m in active_managers:
            rows.append((m, True))
        for m in disabled_managers:
            rows.append((m, False))
        return rows

    def get_title_text():
        return [
            ("class:title", " 📦 Package Manager Priority & Status Manager "),
            ("class:sub", f" [Platform: {plat}] "),
        ]

    def get_body_text():
        nonlocal selected_idx
        rows = get_all_rows()
        if not rows:
            return [("class:normal", "No package managers found.\n")]

        if selected_idx >= len(rows):
            selected_idx = max(0, len(rows) - 1)

        lines = []
        lines.append(("class:header", "  PRIORITY   MANAGER           STATUS         DETAILS\n"))
        lines.append(("class:separator", " ──────────────────────────────────────────────────────────────────────────\n"))

        for idx, (mgr, is_active) in enumerate(rows):
            is_cur = (idx == selected_idx)
            info_str, is_present = _get_manager_info(mgr, custom_paths)

            if is_active:
                p_rank = active_managers.index(mgr) + 1
                p_str = f"#{p_rank:<8}"
            else:
                p_str = "-       "

            if is_cur and is_moving:
                cursor = "⇕ "
                cur_style = "class:moving"
                status_badge = "[MOVING]"
            elif is_cur:
                cursor = "❯ "
                cur_style = "class:selected"
                status_badge = "Active" if is_active else "Disabled"
            else:
                cursor = "  "
                cur_style = "class:normal" if is_active else "class:disabled_item"
                status_badge = "Active" if is_active else "Disabled"

            # Format status badge
            if is_active:
                status_tag = f"● {status_badge:<10}"
            else:
                status_tag = f"○ {status_badge:<10}"

            # Executable detail
            if is_present:
                det_str = f"✔ {info_str}"
            else:
                det_str = f"✘ {info_str}"

            mgr_display = f"{mgr:<17}"
            row_text = f"{cursor}{p_str} {mgr_display} {status_tag} {det_str[:28]}\n"

            if is_cur and is_moving:
                lines.append(("class:moving", row_text))
            elif is_cur:
                lines.append(("class:selected", row_text))
            elif not is_active:
                lines.append(("class:disabled_item", row_text))
            else:
                lines.append(("class:normal", row_text))

        lines.append(("class:separator", " ──────────────────────────────────────────────────────────────────────────\n"))
        if status_msg:
            lines.append(("class:status", f" {status_msg}\n"))

        # Footer hints
        if is_moving:
            lines.append(("class:help_moving", " [↑/↓] Move Position   [Space/Enter] Place Item   [1-9] Jump to Rank\n"))
        else:
            lines.append(("class:help", " [↑/↓] Navigate  [Space] Pick Up/Drop  [1-9] Set Rank  [d/e] Enable/Disable  [q/Enter] Save\n"))

        return lines

    kb = KeyBindings()

    @kb.add("up")
    @kb.add("k")
    def _on_up(event):
        nonlocal selected_idx, status_msg
        rows = get_all_rows()
        if not rows:
            return
        status_msg = ""
        if is_moving:
            # Reorder within active managers
            if selected_idx < len(active_managers) and selected_idx > 0:
                active_managers[selected_idx], active_managers[selected_idx - 1] = (
                    active_managers[selected_idx - 1],
                    active_managers[selected_idx],
                )
                selected_idx -= 1
        else:
            selected_idx = (selected_idx - 1) % len(rows)

    @kb.add("down")
    @kb.add("j")
    def _on_down(event):
        nonlocal selected_idx, status_msg
        rows = get_all_rows()
        if not rows:
            return
        status_msg = ""
        if is_moving:
            # Reorder within active managers
            if selected_idx < len(active_managers) - 1:
                active_managers[selected_idx], active_managers[selected_idx + 1] = (
                    active_managers[selected_idx + 1],
                    active_managers[selected_idx],
                )
                selected_idx += 1
        else:
            selected_idx = (selected_idx + 1) % len(rows)

    @kb.add("space")
    def _on_space(event):
        nonlocal is_moving, status_msg
        rows = get_all_rows()
        if not rows:
            return
        if is_moving:
            is_moving = False
            status_msg = f"Placed '{rows[selected_idx][0]}' at current position."
        else:
            mgr, is_active = rows[selected_idx]
            if not is_active:
                status_msg = f"Cannot grab disabled manager '{mgr}'. Press 'e' to enable first."
                return
            is_moving = True
            status_msg = f"Grabbed '{mgr}'. Use [↑/↓] to move, [Space/Enter] to place."

    # Direct move shortcuts (u / d)
    @kb.add("u")
    def _on_move_up(event):
        nonlocal selected_idx, status_msg
        if selected_idx < len(active_managers) and selected_idx > 0:
            active_managers[selected_idx], active_managers[selected_idx - 1] = (
                active_managers[selected_idx - 1],
                active_managers[selected_idx],
            )
            selected_idx -= 1
            status_msg = f"Moved '{active_managers[selected_idx]}' up to #{selected_idx + 1}."

    @kb.add("d", filter=None)
    def _on_d_key(event):
        nonlocal status_msg, is_moving, selected_idx
        # If moving, 'd' moves down; otherwise 'd' toggles enable/disable
        if is_moving:
            if selected_idx < len(active_managers) - 1:
                active_managers[selected_idx], active_managers[selected_idx + 1] = (
                    active_managers[selected_idx + 1],
                    active_managers[selected_idx],
                )
                selected_idx += 1
                status_msg = f"Moved '{active_managers[selected_idx]}' down to #{selected_idx + 1}."
            return

        # Toggle enable/disable
        _toggle_selected()

    @kb.add("e")
    def _on_enable_toggle(event):
        _toggle_selected()

    def _toggle_selected():
        nonlocal selected_idx, is_moving, status_msg
        rows = get_all_rows()
        if not rows:
            return
        is_moving = False
        mgr, is_active = rows[selected_idx]

        if is_active:
            active_managers.remove(mgr)
            if mgr not in disabled_managers:
                disabled_managers.append(mgr)
            status_msg = f"Disabled '{mgr}'."
            # Cursor stays or adjusts
            rows_now = get_all_rows()
            selected_idx = min(selected_idx, len(rows_now) - 1)
        else:
            disabled_managers.remove(mgr)
            if mgr not in active_managers:
                active_managers.append(mgr)
            status_msg = f"Enabled '{mgr}' at priority #{len(active_managers)}."
            # Cursor moves to the newly enabled item
            selected_idx = len(active_managers) - 1

    # Number keys 1-9 to set rank directly
    for num in range(1, 10):
        def _make_num_handler(target_rank: int):
            def _handler(event):
                nonlocal selected_idx, is_moving, status_msg
                rows = get_all_rows()
                if not rows:
                    return
                mgr, is_active = rows[selected_idx]
                if not is_active:
                    status_msg = f"'{mgr}' is disabled. Press 'e' to enable before ranking."
                    return

                target_idx = target_rank - 1
                if target_idx >= len(active_managers):
                    target_idx = len(active_managers) - 1

                cur_idx = active_managers.index(mgr)
                if cur_idx == target_idx:
                    status_msg = f"'{mgr}' is already at rank #{target_rank}."
                    return

                item = active_managers.pop(cur_idx)
                active_managers.insert(target_idx, item)
                selected_idx = target_idx
                is_moving = False
                status_msg = f"Set '{mgr}' priority to #{target_rank}."
            return _handler

        kb.add(str(num))(_make_num_handler(num))

    @kb.add("enter")
    def _on_enter(event):
        nonlocal is_moving, status_msg
        if is_moving:
            is_moving = False
            rows = get_all_rows()
            status_msg = f"Placed '{rows[selected_idx][0]}' at current position."
        else:
            event.app.exit()

    @kb.add("q")
    @kb.add("escape")
    def _on_exit(event):
        event.app.exit()

    top_bar = VSplit([
        Window(width=1, height=1, char="╭", style="class:border"),
        Window(width=2, height=1, char="─", style="class:border"),
        Window(content=FormattedTextControl(get_title_text), dont_extend_width=True),
        Window(char="─", height=1, style="class:border"),
        Window(width=1, height=1, char="╮", style="class:border"),
    ], height=1)

    term_rows = shutil.get_terminal_size((80, 24)).lines
    body_h = min(len(active_managers) + len(disabled_managers) + 6, max(8, term_rows - 4))

    body_window = Window(
        content=FormattedTextControl(get_body_text),
        height=body_h,
        dont_extend_height=True,
    )

    bottom_bar = VSplit([
        Window(width=1, height=1, char="╰", style="class:border"),
        Window(char="─", height=1, style="class:border"),
        Window(width=1, height=1, char="╯", style="class:border"),
    ], height=1)

    main_panel = VSplit([
        Window(width=1, char="│", style="class:border"),
        body_window,
        Window(width=1, char="│", style="class:border"),
    ])

    layout = Layout(HSplit([top_bar, main_panel, bottom_bar]))

    style = Style.from_dict({
        "border": "fg:#38bdf8",
        "title": "bold fg:#00f0ff bg:#0f172a",
        "sub": "dim fg:#94a3b8 bg:#0f172a",
        "header": "bold fg:#38bdf8",
        "separator": "dim fg:#334155",
        "selected": "bold fg:#00f0ff bg:#1e293b",
        "moving": "bold fg:#fbbf24 bg:#3b2505",
        "normal": "fg:#f1f5f9",
        "disabled_item": "dim fg:#64748b",
        "status": "bold fg:#10b981",
        "help": "dim fg:#94a3b8",
        "help_moving": "bold fg:#f59e0b",
    })

    app = Application(layout=layout, key_bindings=kb, style=style, full_screen=False)
    app.run()

    # Save changes to config
    conf["managers"] = active_managers
    conf["disabled"] = disabled_managers
    plugin_instance.save_config(conf)

    console.print()
    console.print("[bold #10b981]✔ Package manager priority order and status saved successfully![/]")
    return plugin_instance._show_order(console)
