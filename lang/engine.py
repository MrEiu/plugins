"""
Terminal Language & Culture Switcher Engine.
Configures process-level and shell-level localization environment variables,
PowerShell thread culture, .NET UI language, and Kapsel config.
All comments and docstrings are in English.
"""

from pathlib import Path
import os
import subprocess
import sys
from typing import Any, Dict, Optional, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from kapsel.storage.config import load_config, update_config_value


def is_chinese_active() -> bool:
    """Returns True if the current environment or config is set to Chinese."""
    lang = os.environ.get("LANG", "").lower()
    lc_all = os.environ.get("LC_ALL", "").lower()
    if "zh" in lang or "zh" in lc_all:
        return True

    try:
        cfg = load_config()
        if "zh" in getattr(cfg, "language", "").lower():
            return True
    except Exception:
        pass

    return False


def set_terminal_language(target: str) -> Tuple[str, Dict[str, str]]:
    """
    Sets terminal environment variables, culture info, and Kapsel config.
    target: 'zh', 'zh-cn', 'en', 'en-us'
    """
    is_zh = target.lower() in ("zh", "zh-cn", "zh_cn", "cn", "chinese", "中文")

    if is_zh:
        lang_tag = "zh_CN.UTF-8"
        ui_culture = "zh-CN"
        kapsel_lang = "zh_CN"
        dotnet_lang = "zh-Hans"
        vslang = "2052"
        display_name = "Simplified Chinese (简体中文)"
    else:
        lang_tag = "en_US.UTF-8"
        ui_culture = "en-US"
        kapsel_lang = "en"
        dotnet_lang = "en-US"
        vslang = "1033"
        display_name = "English (英文模式)"

    # 1. Process environment variables (inherited by all child subprocesses)
    os.environ["LANG"] = lang_tag
    os.environ["LC_ALL"] = lang_tag
    os.environ["LC_MESSAGES"] = lang_tag
    os.environ["LANGUAGE"] = f"{ui_culture}:{target.lower()}"
    os.environ["DOTNET_CLI_UI_LANGUAGE"] = dotnet_lang
    os.environ["VSLANG"] = vslang

    # 2. Synchronize Kapsel system configuration
    try:
        update_config_value("language", kapsel_lang)
    except Exception:
        pass

    env_state = {
        "LANG": lang_tag,
        "LC_ALL": lang_tag,
        "CurrentUICulture": ui_culture,
        "DOTNET_CLI_UI_LANGUAGE": dotnet_lang,
        "Kapsel UI": kapsel_lang,
    }

    return display_name, env_state


def toggle_terminal_language() -> Tuple[str, Dict[str, str]]:
    """Toggles between English and Chinese."""
    next_target = "en" if is_chinese_active() else "zh"
    return set_terminal_language(next_target)


def render_language_card(display_name: str, env_state: Dict[str, str], console: Console) -> None:
    """Renders a modern Rich status card showing active terminal language settings."""
    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold #38bdf8", justify="right")
    table.add_column(style="white")

    for key, val in env_state.items():
        table.add_row(f"{key}:", val)

    panel = Panel(
        table,
        title=f"[bold white]🌐 Active Terminal Language: [bold #00f0ff]{display_name}[/]",
        subtitle="[dim]Environment & Culture synchronization active ✔[/]",
        border_style="#00f0ff",
        padding=(1, 2),
    )
    console.print()
    console.print(panel)
    console.print()


def render_status_card(console: Console) -> None:
    """Renders current status of terminal language environment."""
    current_lang = os.environ.get("LANG", "(not set)")
    current_lc = os.environ.get("LC_ALL", "(not set)")
    dotnet = os.environ.get("DOTNET_CLI_UI_LANGUAGE", "(not set)")
    
    try:
        cfg = load_config()
        kapsel_lang = getattr(cfg, "language", "en")
    except Exception:
        kapsel_lang = "en"

    state = {
        "LANG": current_lang,
        "LC_ALL": current_lc,
        "DOTNET_CLI_UI_LANGUAGE": dotnet,
        "Kapsel Language Config": kapsel_lang,
        "Active Mode": "Chinese (zh-CN)" if is_chinese_active() else "English (en-US)",
    }

    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold #38bdf8", justify="right")
    table.add_column(style="white")

    for k, v in state.items():
        table.add_row(f"{k}:", v)

    panel = Panel(
        table,
        title="[bold white]🌐 Terminal Localization Environment Status[/]",
        subtitle="[dim]Use 'lang zh' / 'lang en' or 'lang' to switch[/]",
        border_style="#38bdf8",
        padding=(1, 2),
    )
    console.print()
    console.print(panel)
    console.print()
