"""
Kapsel AI Plugin - Interactive Setup Wizard.
Guides users step-by-step through configuring LLM providers and models using OpenAI Python SDK.
Features dual-column interactive selector for providers and dynamically probed models.
All comments and descriptions are in English.
"""

from getpass import getpass
import os
from pathlib import Path
import shutil
import sys
from typing import Any, Dict, List, Optional, Tuple
import unicodedata

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from kapsel.ui.banner import ensure_utf8_io
from .config import (
    DEFAULT_PROVIDERS,
    get_ai_config_file,
    save_ai_config,
    load_ai_config,
    get_provider_models,
)
from .client import AiClient

ensure_utf8_io()


def get_char_width(ch: str) -> int:
    """Returns visual cell width of a character (2 for East Asian Wide/Fullwidth, 1 otherwise)."""
    return 2 if unicodedata.east_asian_width(ch) in ("F", "W") else 1


def get_string_width(s: str) -> int:
    """Calculates total visual terminal columns occupied by string."""
    return sum(get_char_width(c) for c in s)


def fit_text_to_width(s: str, target_width: int) -> str:
    """Pads or truncates text to fit exactly into target_width visual terminal columns."""
    cur_w = 0
    chars: List[str] = []
    for ch in s:
        w = get_char_width(ch)
        if cur_w + w > target_width - 3 and len(s) > len(chars) + 1:
            return "".join(chars) + "..." + " " * max(0, target_width - cur_w - 3)
        chars.append(ch)
        cur_w += w
    return "".join(chars) + " " * max(0, target_width - cur_w)


def _render_fallback_two_column(items: List[str], title: str, con: Console) -> None:
    """Renders two-column table using Rich for non-interactive or fallback mode."""
    table = Table(
        title=f"[bold #00f0ff]🤖 {title}[/]",
        border_style="#0891b2",
        show_header=False,
        expand=True,
    )
    table.add_column("Col 1", style="white", ratio=1)
    table.add_column("Col 2", style="white", ratio=1)
    num_rows = (len(items) + 1) // 2
    for r in range(num_rows):
        i1 = r * 2
        i2 = r * 2 + 1
        t1 = f"[bold #a855f7][{i1 + 1:>2}][/] {items[i1]}"
        t2 = f"[bold #a855f7][{i2 + 1:>2}][/] {items[i2]}" if i2 < len(items) else ""
        table.add_row(t1, t2)
    con.print(table)


def select_two_column_interactive(
    items: List[str],
    title: str,
    subtitle: str = "[↑/↓/←/→] Navigate  |  [Enter] Confirm  |  [Esc/q] Cancel",
    console: Optional[Console] = None,
    default_idx: int = 0,
) -> Optional[int]:
    """
    Renders an interactive two-column selection card.
    Uses prompt_toolkit in interactive TTY consoles with arrow navigation,
    and falls back cleanly to Rich two-column table in non-TTY / CI environments.
    """
    if not items:
        return None

    con = console or Console(legacy_windows=False)

    # Check if TTY is available
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        _render_fallback_two_column(items, title, con)
        try:
            raw = input(f"Enter choice [1-{len(items)}] (default: {default_idx + 1}): ").strip()
            if not raw:
                return default_idx
            idx = int(raw) - 1
            return idx if 0 <= idx < len(items) else default_idx
        except Exception:
            return default_idx

    try:
        from prompt_toolkit.application import Application
        from prompt_toolkit.data_structures import Point
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.layout.containers import HSplit, VSplit, Window
        from prompt_toolkit.layout.controls import FormattedTextControl
        from prompt_toolkit.layout.dimension import Dimension
        from prompt_toolkit.layout.layout import Layout
        from prompt_toolkit.styles import Style

        selected_idx = default_idx if 0 <= default_idx < len(items) else 0
        total_rows = (len(items) + 1) // 2
        result: List[Optional[int]] = [None]

        term_size = shutil.get_terminal_size((80, 24))
        card_w = max(56, min(106, term_size.columns - 4))
        # Inner body width: borders take 2 ("│ " and " │") and divider takes 3 (" │ ") -> 7 total
        inner_w = card_w - 7
        col1_w = inner_w // 2
        col2_w = inner_w - col1_w

        max_visible_rows = max(5, min(14, term_size.lines - 8))
        scroll_top = [0]

        def get_title_text():
            return [
                ("class:border", " "),
                ("class:title", f" 🤖 {title} "),
                ("class:border", " "),
            ]

        def get_body_text():
            nonlocal selected_idx
            cur_row = selected_idx // 2

            if cur_row < scroll_top[0]:
                scroll_top[0] = cur_row
            elif cur_row >= scroll_top[0] + max_visible_rows:
                scroll_top[0] = cur_row - max_visible_rows + 1

            visible_end = min(total_rows, scroll_top[0] + max_visible_rows)
            fragments = []

            for r in range(scroll_top[0], visible_end):
                i1 = r * 2
                i2 = r * 2 + 1

                # Column 1
                is_sel1 = (selected_idx == i1)
                prefix1 = " ▶ " if is_sel1 else "   "
                num_str1 = f"{i1 + 1:>2}. "
                avail1 = max(10, col1_w - 3 - len(num_str1))
                fitted1 = fit_text_to_width(items[i1], avail1)
                full_col1 = fit_text_to_width(f"{prefix1}{num_str1}{fitted1}", col1_w)
                style1 = "class:selected" if is_sel1 else "class:normal"
                fragments.append((style1, full_col1))

                # Divider
                fragments.append(("class:divider", " │ "))

                # Column 2
                if i2 < len(items):
                    is_sel2 = (selected_idx == i2)
                    prefix2 = " ▶ " if is_sel2 else "   "
                    num_str2 = f"{i2 + 1:>2}. "
                    avail2 = max(10, col2_w - 3 - len(num_str2))
                    fitted2 = fit_text_to_width(items[i2], avail2)
                    full_col2 = fit_text_to_width(f"{prefix2}{num_str2}{fitted2}", col2_w)
                    style2 = "class:selected" if is_sel2 else "class:normal"
                    fragments.append((style2, full_col2))
                else:
                    fragments.append(("class:normal", " " * col2_w))

                fragments.append(("", "\n"))

            if fragments and fragments[-1][1] == "\n":
                fragments.pop()
            return fragments

        def get_cursor_pos():
            cur_r = selected_idx // 2
            view_r = max(0, cur_r - scroll_top[0])
            col_x = 1 if (selected_idx % 2 == 0) else (col1_w + 4)
            return Point(x=col_x, y=view_r)

        kb = KeyBindings()

        @kb.add("up")
        def _on_up(event):
            nonlocal selected_idx
            cur_r = selected_idx // 2
            if cur_r > 0:
                selected_idx -= 2

        @kb.add("down")
        def _on_down(event):
            nonlocal selected_idx
            target = selected_idx + 2
            if target < len(items):
                selected_idx = target
            elif selected_idx < len(items) - 1:
                selected_idx = len(items) - 1

        @kb.add("left")
        def _on_left(event):
            nonlocal selected_idx
            if selected_idx % 2 == 1:
                selected_idx -= 1

        @kb.add("right")
        def _on_right(event):
            nonlocal selected_idx
            if selected_idx % 2 == 0 and selected_idx + 1 < len(items):
                selected_idx += 1

        @kb.add("pageup")
        def _on_pageup(event):
            nonlocal selected_idx
            cur_r = selected_idx // 2
            cur_c = selected_idx % 2
            new_r = max(0, cur_r - max_visible_rows)
            selected_idx = min(new_r * 2 + cur_c, len(items) - 1)

        @kb.add("pagedown")
        def _on_pagedown(event):
            nonlocal selected_idx
            cur_r = selected_idx // 2
            cur_c = selected_idx % 2
            new_r = min(total_rows - 1, cur_r + max_visible_rows)
            selected_idx = min(new_r * 2 + cur_c, len(items) - 1)

        @kb.add("home")
        def _on_home(event):
            nonlocal selected_idx
            selected_idx = 0

        @kb.add("end")
        def _on_end(event):
            nonlocal selected_idx
            selected_idx = len(items) - 1

        @kb.add("enter")
        def _on_enter(event):
            result[0] = selected_idx
            event.app.exit()

        @kb.add("escape")
        @kb.add("q")
        def _on_cancel(event):
            result[0] = None
            event.app.exit()

        top_bar = VSplit([
            Window(width=1, height=1, char="╭", style="class:border"),
            Window(width=2, height=1, char="─", style="class:border"),
            Window(content=FormattedTextControl(get_title_text), dont_extend_width=True),
            Window(char="─", height=1, style="class:border"),
            Window(width=1, height=1, char="╮", style="class:border"),
        ], height=1)

        actual_body_h = min(total_rows, max_visible_rows)
        body_window = Window(
            content=FormattedTextControl(get_body_text, get_cursor_position=get_cursor_pos, focusable=True),
            wrap_lines=False,
            height=Dimension(min=3, max=max(3, actual_body_h)),
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
                ("class:help", f"  {subtitle}")
            ]),
            height=1,
            style="class:help",
        )

        app_layout = Layout(HSplit([top_bar, mid_bar, bot_bar, help_bar]))

        style = Style.from_dict({
            "border": "fg:#0891b2",
            "title": "bold fg:#00f0ff",
            "selected": "bold fg:#00f0ff bg:#1e293b",
            "normal": "fg:#f1f5f9",
            "divider": "fg:#334155",
            "help": "dim fg:#94a3b8",
        })

        app = Application(layout=app_layout, key_bindings=kb, style=style, full_screen=False)
        app.run()
        return result[0]

    except Exception:
        # Graceful fallback to rich 2-column table
        _render_fallback_two_column(items, title, con)
        try:
            raw = input(f"Enter choice [1-{len(items)}] (default: {default_idx + 1}): ").strip()
            if not raw:
                return default_idx
            idx = int(raw) - 1
            return idx if 0 <= idx < len(items) else default_idx
        except Exception:
            return default_idx


def run_ai_setup_wizard(console: Optional[Console] = None) -> int:
    """
    Runs an interactive terminal wizard to configure an AI provider and models.
    Zero static preset models are used. Dynamically probes endpoint with error alerts.
    Saves to ~/.kapsel/ai/config.yaml and verifies connectivity.
    """
    con = console or Console(legacy_windows=False)

    try:
        # 1. Choice of provider via Two-Column Selector
        provider_names = [prov["name"] for prov in DEFAULT_PROVIDERS]
        choice_idx = select_two_column_interactive(
            items=provider_names,
            title="Select AI Model Provider (双列选择)",
            subtitle="[↑/↓/←/→] Navigate  |  [Enter] Confirm  |  [Esc/q] Cancel",
            console=con,
        )

        if choice_idx is None:
            con.print("\n[dim]Setup aborted.[/]")
            return 1

        selected = DEFAULT_PROVIDERS[choice_idx]
        con.print(f"\n[bold #10b981]✔ Selected:[/] [white]{selected['name']}[/]\n")

        # Outer credential loop in case user wants to re-enter credentials on probe failure
        api_base = selected["api_base"]
        model_name = ""

        while True:
            # 2. Base URL
            if selected["id"] == "custom":
                raw_base = input(f"Enter API Base URL [{api_base or 'http://localhost:8000/v1'}]: ").strip()
                api_base = raw_base or api_base or "http://localhost:8000/v1"
            else:
                prompt_base = input(f"API Base URL [{api_base}]: ").strip()
                if prompt_base:
                    api_base = prompt_base

            # 3. API Key
            api_key = ""
            if selected["requires_key"]:
                api_key = getpass(selected["key_prompt"]).strip()
                if not api_key:
                    con.print("[yellow]Warning: Empty API key provided. Requests may fail if authentication is required.[/]")
            else:
                con.print("[dim]No API key required for local provider.[/]")

            # 4. Model Selection (Dynamic /models probe with zero default fallback)
            con.print("\n[dim]Probing available models from endpoint...[/]")
            available_models, probe_err = get_provider_models(
                provider_id=selected["id"],
                api_base=api_base,
                api_key=api_key,
                timeout=7.0,
            )

            if not available_models or probe_err:
                con.print(Panel(
                    f"[bold #f43f5e]✖ API Verification / Model Probe Failed:[\\/]\n"
                    f"  [white]{probe_err or 'The provider endpoint returned zero available models.'}[\\/]\n\n"
                    f"[dim]Please check your API Key, network proxy, or endpoint URL.[\\/]",
                    title="[bold #f43f5e]API Error[/]",
                    border_style="#f43f5e",
                ))

                con.print("\n[bold white]What would you like to do?[/]")
                con.print("  [bold #a855f7][1][/] [white]✏️  Manually enter model name[/]")
                con.print("  [bold #a855f7][2][/] [white]🔄 Re-enter API Key and Base URL[/]")
                con.print("  [bold #a855f7][3][/] [white]❌ Abort setup[/]")

                recovery = input("\nEnter choice [1-3] (default: 1): ").strip() or "1"
                if recovery == "2":
                    con.print("\n[dim]Re-entering credentials...[/]\n")
                    continue
                elif recovery == "3":
                    con.print("\n[dim]Setup aborted.[/]")
                    return 1
                else:
                    manual_model = input("Enter model name (e.g. deepseek-chat): ").strip()
                    if not manual_model:
                        con.print("[yellow]No model name entered. Setup aborted.[/]")
                        return 1
                    model_name = manual_model
                    break
            else:
                con.print(f"[bold #10b981]✔ Successfully retrieved {len(available_models)} models from provider![/]\n")

                model_choices = list(available_models)
                model_choices.append("✏️  [Manual Entry / Other Model]")

                sel_model_idx = select_two_column_interactive(
                    items=model_choices,
                    title=f"Select Model for {selected['name']} ({len(available_models)} available)",
                    subtitle="[↑/↓/←/→] Navigate  |  [Enter] Confirm  |  [Esc/q] Cancel",
                    console=con,
                )

                if sel_model_idx is None:
                    con.print("\n[dim]Setup aborted.[/]")
                    return 1

                if sel_model_idx == len(model_choices) - 1:
                    manual_model = input("Enter custom model name: ").strip()
                    if not manual_model:
                        con.print("[yellow]No model name entered. Setup aborted.[/]")
                        return 1
                    model_name = manual_model
                else:
                    model_name = model_choices[sel_model_idx]
                break

    except (ValueError, KeyboardInterrupt, EOFError):
        con.print("\n[dim]Setup aborted.[/]")
        return 1

    # 5. Build configuration structure
    cfg_data: Dict[str, Any] = {
        "provider": selected["id"],
        "provider_name": selected["name"],
        "api_base": api_base,
        "api_key": api_key,
        "model": model_name,
        "temperature": 0.1,
    }

    # 6. Save configuration to Kapsel data directory
    save_ai_config(cfg_data)
    target_file = get_ai_config_file()

    con.print(f"\n[bold #10b981]✔ Configuration successfully saved![/]")
    con.print(f"[dim]Config file: {target_file}[/]")

    # 7. Verification test using AiClient
    con.print("\n[dim]Testing connectivity with configured model endpoint...[/]")
    try:
        client = AiClient(api_base=api_base, api_key=api_key, model=model_name, timeout=12.0)
        res = client.chat_completion(
            messages=[{"role": "user", "content": "Respond with 'pong' only"}],
            temperature=0.1,
        )
        if res:
            con.print(f"[bold #10b981]✔ Model responded successfully:[/] [dim]{res[:60]}[/]")
            con.print("\n[bold #10b981]✨ AI setup complete![/] You can now use:")
            con.print("  [bold #00f0ff]kps ai <prompt>[/]     - Natural language to command")
            con.print("  [bold #00f0ff]kps ai fix[/]          - Auto-diagnose and fix last failed command")
            con.print("  [bold #00f0ff]kps ai explain [cmd][/] - Dissect command flags and parameters\n")
            return 0
        else:
            con.print("[yellow]Notice: Model connected but returned empty response. Please verify settings.[/]\n")
            return 0
    except Exception as e:
        con.print(f"[yellow]Notice: Configuration written, but test ping returned warning: {e}[/]")
        con.print("[dim]You can test again anytime with:[/] [bold #00f0ff]kps ai config test[/]\n")
        return 0
