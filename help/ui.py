"""
UI and Interactive Selector Helper for Help Plugin.
Provides prompt_toolkit interactive menus, styled tables, and clipboard helpers.
All comments and docstrings are in English.
"""

import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Callable, Dict, List, Optional, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

try:
    from prompt_toolkit.application import Application
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout import Layout, Window
    from prompt_toolkit.layout.controls import FormattedTextControl
    from prompt_toolkit.styles import Style
    from kapsel.ui.prompt import get_safe_output
except ImportError:
    get_safe_output = lambda: None

HELP_MENU_STYLE = Style.from_dict({
    "help.header": "bold #00f0ff",
    "help.banner": "italic #94a3b8",
    "help.cursor": "bold #10b981",
    "help.item_selected": "bold #ffffff bg:#334155",
    "help.item_unselected": "#cbd5e1",
    "help.tag": "bold #38bdf8",
    "help.desc": "#94a3b8",
    "help.footer": "dim #94a3b8",
    "help.footer_key": "bold #38bdf8",
})


def copy_to_clipboard(text: str) -> bool:
    """Copies text to system clipboard cross-platform."""
    try:
        if sys.platform == "win32":
            subprocess.run(["clip"], input=text.encode("utf-16le"), check=True)
            return True
        elif sys.platform == "darwin":
            subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True)
            return True
        else:
            for tool in ["wl-copy", "xclip", "xsel"]:
                if shutil.which(tool):
                    cmd = [tool, "-selection", "clipboard"] if tool == "xclip" else [tool]
                    subprocess.run(cmd, input=text.encode("utf-8"), check=True)
                    return True
    except Exception:
        pass
    return False


def open_in_file_manager(target_path: str) -> bool:
    """Opens directory containing target_path in host file manager."""
    try:
        p = Path(target_path).resolve()
        folder = str(p.parent if p.is_file() else p)
        if sys.platform == "win32":
            os.startfile(folder)
            return True
        elif sys.platform == "darwin":
            subprocess.run(["open", folder], check=True)
            return True
        else:
            subprocess.run(["xdg-open", folder], check=True)
            return True
    except Exception:
        return False


def select_interactive_item(
    items: List[Dict[str, Any]],
    title: str = "Select an Item:",
    key_labels: Optional[List[Tuple[str, str]]] = None,
    extra_bindings: Optional[Dict[str, Callable[[int, Any], None]]] = None,
) -> Optional[Tuple[int, str]]:
    """
    Presents an interactive prompt_toolkit menu for items with custom keybindings.
    Returns (selected_index, action_key) or None if cancelled.
    """
    if not items or not sys.stdin.isatty():
        return None

    selected_idx = 0
    total = len(items)

    def get_tokens() -> List[Tuple[str, str]]:
        tokens: List[Tuple[str, str]] = [
            ("class:help.header", f"\n{title}\n"),
        ]

        # Display window
        window_size = 12
        start_idx = max(0, min(selected_idx - window_size // 2, total - window_size))
        end_idx = min(total, start_idx + window_size)

        for idx in range(start_idx, end_idx):
            item = items[idx]
            is_selected = (idx == selected_idx)
            label = item.get("label", "")
            desc = item.get("desc", "")
            tag = item.get("tag", "")

            tag_str = f"[{tag}] " if tag else ""

            if is_selected:
                tokens.append(("class:help.cursor", " ❯ "))
                tokens.append(("class:help.item_selected", f" {tag_str}{label} "))
                if desc:
                    tokens.append(("class:help.desc", f" {desc}\n"))
                else:
                    tokens.append(("", "\n"))
            else:
                tokens.append(("", "   "))
                if tag_str:
                    tokens.append(("class:help.tag", tag_str))
                tokens.append(("class:help.item_unselected", label))
                if desc:
                    tokens.append(("class:help.desc", f"  {desc}\n"))
                else:
                    tokens.append(("", "\n"))

        tokens.append(("class:help.footer", "\n "))
        tokens.append(("class:help.footer_key", "[↑/↓]"))
        tokens.append(("class:help.footer", " Navigate · "))

        labels = key_labels or [("[Enter]", "Select"), ("[Esc]", "Cancel")]
        for key_name, action_label in labels:
            tokens.append(("class:help.footer_key", f" {key_name}"))
            tokens.append(("class:help.footer", f" {action_label} ·"))

        tokens.append(("", "\n"))
        return tokens

    kb = KeyBindings()

    @kb.add("up")
    def _up(event: Any) -> None:
        nonlocal selected_idx
        selected_idx = (selected_idx - 1) % total
        event.app.invalidate()

    @kb.add("down")
    def _down(event: Any) -> None:
        nonlocal selected_idx
        selected_idx = (selected_idx + 1) % total
        event.app.invalidate()

    @kb.add("enter")
    def _enter(event: Any) -> None:
        event.app.exit(result=(selected_idx, "enter"))

    @kb.add("escape")
    @kb.add("c-c")
    def _cancel(event: Any) -> None:
        event.app.exit(result=None)

    # Custom key bindings
    if extra_bindings:
        for k_trigger, handler in extra_bindings.items():
            def _make_handler(trigger: str, fn: Callable[[int, Any], None]):
                def _bound(event: Any) -> None:
                    event.app.exit(result=(selected_idx, trigger))
                return _bound
            kb.add(k_trigger)(_make_handler(k_trigger, handler))

    try:
        app = Application(
            layout=Layout(Window(FormattedTextControl(get_tokens))),
            key_bindings=kb,
            style=HELP_MENU_STYLE,
            full_screen=False,
            output=get_safe_output(),
        )
        return app.run()
    except Exception:
        return None
