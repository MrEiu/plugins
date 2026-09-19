"""
Terminal Language Switcher Plugin for Kapsel.
Provides zero-latency switching between Chinese and English environments.
Synchronizes LANG, LC_ALL, PowerShell thread culture, .NET UI language, and Kapsel UI.
All comments and docstrings are in English.
"""

from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple

from rich.console import Console

from kapsel.core.plugin.base import KapselPlugin, PluginManifest
from kapsel.core.plugin.context import PluginContext
from kapsel.core.plugin.hooks import HookType

try:
    from .engine import (
        render_language_card,
        render_status_card,
        set_terminal_language,
        toggle_terminal_language,
    )
except ImportError:
    from plugins.lang.engine import (
        render_language_card,
        render_status_card,
        set_terminal_language,
        toggle_terminal_language,
    )


class LangPlugin(KapselPlugin):
    """
    Kapsel Lang Plugin:
    Instant terminal language, shell culture, and CLI localization switcher.
    """

    manifest = PluginManifest(
        id="lang",
        name="Lang",
        version="0.1.0",
        description="Instant terminal language, shell culture, and CLI localization switcher.",
        author="Kapsel Team",
        homepage="https://github.com/MrEiu/plugins/tree/master/lang",
        min_kapsel_version="0.1.0",
        tags=["lang", "locale", "i18n", "culture", "chinese", "english"],
    )

    def __init__(self) -> None:
        super().__init__()
        self.context: Optional[PluginContext] = None

    def on_load(self, context: PluginContext) -> None:
        self.context = context

        # 1. Pre-execution filter: intercepts 'lang' shortcut
        context.register_hook(HookType.FILTER_COMMAND, self.filter_command)

        # 2. Dynamic autocompletion for lang subcommands
        context.register_hook(HookType.PROVIDE_COMPLETIONS, self.provide_completions)

        # 3. Register functional command under kps namespace
        context.register_kps_command(
            name="lang",
            handler=self.handle_lang,
            help_text="Switch terminal environment language and culture (zh/en/toggle)",
            usage="kps lang [zh|en|toggle|status]",
            scope="feature",
        )

    def handle_lang(self, args: List[str], console: Optional[Console] = None) -> int:
        """Main handler for 'kps lang' or 'lang'."""
        con = console or Console()

        if not args:
            # No args: toggle language
            name, env_state = toggle_terminal_language()
            render_language_card(name, env_state, con)
            return 0

        target = args[0].lower()

        if target in ("-h", "--help", "help"):
            self._render_help(con)
            return 0

        if target in ("status", "info", "-s"):
            render_status_card(con)
            return 0

        if target in ("toggle", "-t"):
            name, env_state = toggle_terminal_language()
            render_language_card(name, env_state, con)
            return 0

        if target in ("zh", "zh-cn", "zh_cn", "cn", "chinese", "中文"):
            name, env_state = set_terminal_language("zh")
            render_language_card(name, env_state, con)
            return 0

        if target in ("en", "en-us", "en_us", "us", "english", "英文"):
            name, env_state = set_terminal_language("en")
            render_language_card(name, env_state, con)
            return 0

        con.print(f"[bold #f43f5e]Unknown language option:[/] '{target}'. Use 'zh', 'en', 'toggle', or 'status'.")
        return 1

    def filter_command(self, raw_command: str) -> Tuple[bool, str]:
        """
        Intercepts:
        1. 'lang [args]' -> direct execution
        2. 'kps lang [args]' -> direct execution
        """
        stripped = raw_command.strip()
        if not stripped:
            return False, raw_command

        tokens = stripped.split()
        prefix = tokens[0].lower()

        if prefix == "lang":
            con = Console()
            self.handle_lang(tokens[1:], con)
            return True, ""

        if stripped.lower().startswith("kps lang"):
            con = Console()
            self.handle_lang(tokens[2:], con)
            return True, ""

        return False, raw_command

    def provide_completions(self, text_before_cursor: str) -> List[Dict[str, Any]]:
        """Provides autocompletions when typing 'lang ' or 'kps lang '."""
        stripped = text_before_cursor.lstrip()
        matched = False
        for p in ("kps lang ", "lang "):
            if stripped.startswith(p):
                matched = True
                remainder = stripped[len(p):]
                break

        if not matched:
            return []

        subcommands = [
            {"text": "zh", "display": "zh", "display_meta": "Switch to Simplified Chinese (zh-CN)"},
            {"text": "en", "display": "en", "display_meta": "Switch to English (en-US)"},
            {"text": "toggle", "display": "toggle", "display_meta": "Toggle between Chinese and English"},
            {"text": "status", "display": "status", "display_meta": "Display current localization status"},
        ]

        candidates = []
        for sub in subcommands:
            if sub["text"].startswith(remainder.lower()):
                candidates.append({
                    "text": sub["text"],
                    "display": sub["display"],
                    "display_meta": sub["display_meta"],
                    "start_position": -len(remainder),
                })
        return candidates

    def _render_help(self, con: Console) -> None:
        """Renders help manual for lang plugin."""
        con.print("\n[bold #00f0ff]Kapsel Lang - Terminal Language & Culture Switcher[/]")
        con.print("[dim]Instant switching of shell culture, LANG, LC_ALL, and Kapsel UI.[/]\n")
        con.print("[bold white]Usage:[/]")
        con.print("  [#38bdf8]lang[/]               Toggle between Chinese and English")
        con.print("  [#38bdf8]lang zh[/]            Switch to Simplified Chinese (zh-CN)")
        con.print("  [#38bdf8]lang en[/]            Switch to English (en-US)")
        con.print("  [#38bdf8]lang status[/]        View active terminal locale and culture settings\n")


Plugin = LangPlugin
