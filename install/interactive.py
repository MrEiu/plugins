"""
Interactive Package Confirmation Selector for Kapsel Install Plugin.
Prevents accidental installation of stranger/same-name packages by providing
a secondary confirmation menu with arrow-key navigation and risk alerts.

All comments and docstrings are in English.
"""

import sys
from typing import List, Optional

from rich.console import Console
from rich.panel import Panel

from .streaming_search import SearchItem


def select_package_interactive(
    candidates: List[SearchItem],
    console: Optional[Console] = None,
) -> Optional[SearchItem]:
    """
    Presents an interactive menu to let the user select and confirm the exact package
    before installation proceeds.
    Supports arrow-key navigation via prompt_toolkit, with a clean numeric fallback.
    """
    con = console or Console(legacy_windows=False)

    if not candidates:
        con.print("[yellow]No packages available to select.[/]")
        return None

    # If single exact match and high priority, still offer confirmation
    con.print("[bold #00f0ff]🎯 Select a package to install:[/]")
    con.print("[dim]Use arrow keys or enter the candidate number. Press 'q' or Esc to cancel.[/]\n")

    # Check if TTY is attached
    if not sys.stdin.isatty():
        return _numeric_selection_fallback(candidates, con)

    try:
        from prompt_toolkit.application import Application
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.layout.containers import HSplit, Window
        from prompt_toolkit.layout.controls import FormattedTextControl
        from prompt_toolkit.layout.layout import Layout
        from prompt_toolkit.styles import Style

        selected_idx = 0
        total = len(candidates)
        result: List[Optional[SearchItem]] = [None]

        def get_menu_text():
            lines = []
            for i, item in enumerate(candidates):
                is_cur = (i == selected_idx)
                prefix = " ❯ " if is_cur else "   "
                rec_tag = " [★ RECOMMENDED]" if item.is_recommended else ""
                
                # Check for suspicious cross-ecosystem package (e.g. low priority pip package when rust tool was sought)
                warn_tag = ""
                if item.manager == "pip" and not item.is_recommended:
                    warn_tag = " (⚠ Python Package)"

                mgr_label = f"[{item.manager.upper()}]"
                ver_label = f"(v{item.version})" if item.version else ""
                desc_label = f" - {item.description[:40]}..." if item.description else ""

                line_str = f"{prefix}{mgr_label:<9} {item.package_id:<20} {ver_label:<10}{rec_tag}{warn_tag}{desc_label}"

                if is_cur:
                    lines.append(("class:selected", line_str + "\n"))
                else:
                    lines.append(("class:normal", line_str + "\n"))

            lines.append(("\nclass:help", " [↑/↓] Navigate  |  [Enter] Confirm  |  [Esc/q] Cancel\n"))
            return lines

        kb = KeyBindings()

        @kb.add("up")
        def _on_up(event):
            nonlocal selected_idx
            selected_idx = (selected_idx - 1) % total

        @kb.add("down")
        def _on_down(event):
            nonlocal selected_idx
            selected_idx = (selected_idx + 1) % total

        @kb.add("enter")
        def _on_enter(event):
            result[0] = candidates[selected_idx]
            event.app.exit()

        @kb.add("escape")
        @kb.add("q")
        def _on_cancel(event):
            result[0] = None
            event.app.exit()

        style = Style.from_dict({
            "selected": "bold fg:#00f0ff bg:#1e293b",
            "normal": "fg:#e2e8f0",
            "help": "dim fg:#94a3b8",
        })

        layout = Layout(HSplit([Window(content=FormattedTextControl(get_menu_text))]))
        app = Application(layout=layout, key_bindings=kb, style=style, full_screen=False)
        app.run()

        return result[0]

    except Exception:
        # Graceful fallback to numeric input
        return _numeric_selection_fallback(candidates, con)


def _numeric_selection_fallback(candidates: List[SearchItem], con: Console) -> Optional[SearchItem]:
    """Fallback interactive prompt using plain terminal input."""
    for idx, item in enumerate(candidates, 1):
        rec_tag = " [bold #10b981]★ RECOMMENDED[/]" if item.is_recommended else ""
        warn_tag = " [bold yellow](⚠ Python Package)[/]" if (item.manager == "pip" and not item.is_recommended) else ""
        ver_str = f"v{item.version}" if item.version else ""
        con.print(f"  [bold cyan][{idx}][/] [{item.manager}] [bold white]{item.package_id}[/] {ver_str}{rec_tag}{warn_tag}")
        if item.description:
            con.print(f"      [dim]{item.description[:60]}[/]")

    con.print("")
    try:
        choice = input(f"Enter selection [1-{len(candidates)}] or 'q' to cancel: ").strip()
        if choice.lower() in ("q", "quit", "exit", ""):
            return None
        val = int(choice)
        if 1 <= val <= len(candidates):
            return candidates[val - 1]
    except Exception:
        pass

    return None
