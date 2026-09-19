"""
Interactive Configuration and Cache Cleaner for Kapsel Mend Plugin.
Scans temporary files, historical logs, backup configs, and cache directories
with interactive multi-selection and safe confirmation.

All comments and docstrings are in English.
"""

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import sys
from typing import Dict, List, Optional, Set, Tuple

from rich.console import Console
from rich.table import Table

from kapsel.storage.config import get_kapsel_dir


@dataclass
class CleanableCategory:
    key: str
    name: str
    description: str
    paths: List[Path]
    total_bytes: int
    is_safe: bool = True  # Safe temporary files vs user databases

    @property
    def formatted_size(self) -> str:
        b = self.total_bytes
        for unit in ["B", "KB", "MB", "GB"]:
            if b < 1024.0:
                return f"{b:.1f} {unit}"
            b /= 1024.0
        return f"{b:.1f} TB"


def _get_dir_size(path: Path) -> int:
    """Calculates total size of a directory or file in bytes."""
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    total = 0
    try:
        for root, _, files in os.walk(path):
            for f in files:
                fp = Path(root) / f
                try:
                    total += fp.stat().st_size
                except Exception:
                    pass
    except Exception:
        pass
    return total


def scan_cleanable_targets() -> List[CleanableCategory]:
    """
    Scans Kapsel home directory (~/.kapsel) for cleanable categories.
    """
    kapsel_dir = get_kapsel_dir()
    categories: List[CleanableCategory] = []

    # 1. Historical Session Logs (~/.kapsel/logs/*.log)
    logs_dir = kapsel_dir / "logs"
    log_files: List[Path] = []
    if logs_dir.is_dir():
        for p in logs_dir.glob("*.log"):
            if p.is_file():
                log_files.append(p)
    if log_files:
        sz = sum(f.stat().st_size for f in log_files)
        categories.append(CleanableCategory(
            key="logs",
            name="Session & Debug Logs",
            description=f"Log files stored in {logs_dir}",
            paths=log_files,
            total_bytes=sz,
            is_safe=True,
        ))

    # 2. Temporary Downloads & Leftover Binaries (~/.kapsel/bin/download_*, *.tmp)
    bin_dir = kapsel_dir / "bin"
    temp_bins: List[Path] = []
    if bin_dir.is_dir():
        for pattern in ["download_*", "*.tmp", "*.part", "*.download"]:
            for p in bin_dir.glob(pattern):
                temp_bins.append(p)
    if temp_bins:
        sz = sum(_get_dir_size(p) for p in temp_bins)
        categories.append(CleanableCategory(
            key="temp_bins",
            name="Temporary Binary Downloads",
            description="Partial downloads and leftover archives in ~/.kapsel/bin",
            paths=temp_bins,
            total_bytes=sz,
            is_safe=True,
        ))

    # 3. Backup Configuration Snapshots (~/.kapsel/config*.bak, *.old)
    backup_configs: List[Path] = []
    for pattern in ["*.bak", "*.old", "*backup*.yaml", "*backup*.yml"]:
        for p in kapsel_dir.glob(pattern):
            if p.is_file():
                backup_configs.append(p)
    if backup_configs:
        sz = sum(f.stat().st_size for f in backup_configs)
        categories.append(CleanableCategory(
            key="config_backups",
            name="Stale Configuration Backups",
            description="Historical config backups (*.bak, *.old)",
            paths=backup_configs,
            total_bytes=sz,
            is_safe=True,
        ))

    # 4. Plugin Cache & Temp Directories (~/.kapsel/plugins_data/*/cache)
    plugins_data = kapsel_dir / "plugins_data"
    plugin_caches: List[Path] = []
    if plugins_data.is_dir():
        for p in plugins_data.glob("*/cache"):
            if p.is_dir():
                plugin_caches.append(p)
        for p in plugins_data.glob("*/temp"):
            if p.is_dir():
                plugin_caches.append(p)
    if plugin_caches:
        sz = sum(_get_dir_size(p) for p in plugin_caches)
        categories.append(CleanableCategory(
            key="plugins_cache",
            name="Plugin Caches & Temp Directories",
            description="Plugin-generated temporary caches in ~/.kapsel/plugins_data",
            paths=plugin_caches,
            total_bytes=sz,
            is_safe=True,
        ))

    # 5. Compiled Python Bytecode Caches (~/.kapsel/**/__pycache__)
    pycaches: List[Path] = []
    if kapsel_dir.is_dir():
        for p in kapsel_dir.glob("**/__pycache__"):
            if p.is_dir():
                pycaches.append(p)
    if pycaches:
        sz = sum(_get_dir_size(p) for p in pycaches)
        categories.append(CleanableCategory(
            key="pycache",
            name="Python Bytecode Caches (__pycache__)",
            description="Precompiled Python bytecode in ~/.kapsel",
            paths=pycaches,
            total_bytes=sz,
            is_safe=True,
        ))

    # 6. Shell Command History Database (~/.kapsel/user.db or history.db)
    history_files: List[Path] = []
    for hname in ["user.db", "history.db", "history.sqlite"]:
        hp = kapsel_dir / hname
        if hp.is_file():
            history_files.append(hp)
    if history_files:
        sz = sum(f.stat().st_size for f in history_files)
        categories.append(CleanableCategory(
            key="history",
            name="Command History Database (user.db)",
            description="Saved prompt command history records",
            paths=history_files,
            total_bytes=sz,
            is_safe=False,
        ))

    return categories


def interactive_select_cleanable_categories(
    categories: List[CleanableCategory],
    console: Optional[Console] = None,
) -> List[CleanableCategory]:
    """
    Renders an interactive checkbox multi-selection menu for selecting
    categories to clean.
    """
    con = console or Console(legacy_windows=False)
    if not categories:
        con.print("[bold #10b981]✨ Your Kapsel environment is spotless! No temporary or backup files found.[/]\n")
        return []

    con.print("\n[bold #00f0ff]🧹 Kapsel Interactive Configuration & Storage Cleaner[/]")
    con.print("[dim]Select the categories of cached or backup files you wish to clean:[/]\n")

    if not sys.stdin.isatty():
        return _numeric_clean_fallback(categories, con)

    try:
        from prompt_toolkit.application import Application
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.layout.containers import HSplit, Window
        from prompt_toolkit.layout.controls import FormattedTextControl
        from prompt_toolkit.layout.layout import Layout
        from prompt_toolkit.styles import Style

        cursor_idx = 0
        # By default, pre-select safe categories, keep sensitive ones unselected
        selected_keys: Set[str] = {c.key for c in categories if c.is_safe}
        confirmed = [False]

        def get_menu_text():
            lines = []
            for i, cat in enumerate(categories):
                is_cursor = (i == cursor_idx)
                is_checked = cat.key in selected_keys
                prefix = " ❯ " if is_cursor else "   "
                checkbox = "[*] " if is_checked else "[ ] "
                count_str = f"({len(cat.paths)} items, {cat.formatted_size})"
                warn_tag = " [⚠ USER DATA]" if not cat.is_safe else ""

                line = f"{prefix}{checkbox}{cat.name:<36} {count_str:<18}{warn_tag} - {cat.description[:40]}\n"

                if is_cursor:
                    lines.append(("class:selected", line))
                elif is_checked:
                    lines.append(("class:checked", line))
                else:
                    lines.append(("class:normal", line))

            lines.append(("\nclass:help", " [↑/↓] Navigate  |  [Space] Toggle  |  [a] Toggle All  |  [Enter] Confirm  |  [Esc/q] Cancel\n"))
            return lines

        kb = KeyBindings()

        @kb.add("up")
        def _up(event):
            nonlocal cursor_idx
            cursor_idx = (cursor_idx - 1) % len(categories)

        @kb.add("down")
        def _down(event):
            nonlocal cursor_idx
            cursor_idx = (cursor_idx + 1) % len(categories)

        @kb.add("space")
        def _toggle(event):
            k = categories[cursor_idx].key
            if k in selected_keys:
                selected_keys.remove(k)
            else:
                selected_keys.add(k)

        @kb.add("a")
        def _toggle_all(event):
            if len(selected_keys) == len(categories):
                selected_keys.clear()
            else:
                selected_keys.update(c.key for c in categories)

        @kb.add("enter")
        def _confirm(event):
            confirmed[0] = True
            event.app.exit()

        @kb.add("escape")
        @kb.add("q")
        def _cancel(event):
            confirmed[0] = False
            event.app.exit()

        style = Style.from_dict({
            "selected": "bold fg:#00f0ff bg:#1e293b",
            "checked": "bold fg:#10b981",
            "normal": "fg:#e2e8f0",
            "help": "dim fg:#94a3b8",
        })

        layout = Layout(HSplit([Window(content=FormattedTextControl(get_menu_text))]))
        app = Application(layout=layout, key_bindings=kb, style=style, full_screen=False)
        app.run()

        if confirmed[0]:
            return [c for c in categories if c.key in selected_keys]
        return []

    except Exception:
        return _numeric_clean_fallback(categories, con)


def _numeric_clean_fallback(
    categories: List[CleanableCategory],
    con: Console,
) -> List[CleanableCategory]:
    """Numbered fallback for non-interactive environments."""
    for idx, c in enumerate(categories, 1):
        warn = " [bold yellow](⚠ USER DATA)[/]" if not c.is_safe else ""
        con.print(f"  [bold cyan][{idx}][/] [bold white]{c.name}[/] ({len(c.paths)} items, {c.formatted_size}){warn}")
        con.print(f"      [dim]{c.description}[/]")

    con.print("")
    try:
        raw = input("Enter category numbers to clean (comma-separated, e.g. 1, 2) or 'q' to cancel: ").strip()
        if raw.lower() in ("q", "quit", "exit", ""):
            return []
        if raw.lower() == "all":
            return categories

        selected = []
        for part in raw.replace(" ", ",").split(","):
            part = part.strip()
            if part.isdigit():
                num = int(part)
                if 1 <= num <= len(categories):
                    selected.append(categories[num - 1])
        return selected
    except Exception:
        return []


def execute_clean(
    selected_categories: List[CleanableCategory],
    console: Optional[Console] = None,
) -> int:
    """
    Deletes the selected categories and reports total space freed.
    """
    con = console or Console(legacy_windows=False)
    if not selected_categories:
        con.print("[dim]No categories selected for cleaning.[/]\n")
        return 0

    total_bytes_freed = 0
    total_items_deleted = 0

    con.print("\n[bold #00f0ff]🗑 Cleaning selected Kapsel files...[/]\n")

    for cat in selected_categories:
        con.print(f"  • Cleaning [bold white]{cat.name}[/] ({len(cat.paths)} targets)...")
        cat_freed = 0
        for p in cat.paths:
            try:
                if p.is_file() or p.is_symlink():
                    sz = p.stat().st_size
                    p.unlink(missing_ok=True)
                    cat_freed += sz
                    total_items_deleted += 1
                elif p.is_dir():
                    sz = _get_dir_size(p)
                    shutil.rmtree(p, ignore_errors=True)
                    cat_freed += sz
                    total_items_deleted += 1
            except Exception as e:
                con.print(f"    [dim yellow]Could not delete {p}: {e}[/]")

        total_bytes_freed += cat_freed
        con.print(f"    [bold #10b981]✔ Freed {CleanableCategory('', '', '', [], cat_freed).formatted_size}[/]")

    freed_str = CleanableCategory("", "", "", [], total_bytes_freed).formatted_size
    con.print(f"\n[bold #10b981]✔ Cleanup Finished: {total_items_deleted} items removed, {freed_str} disk space reclaimed![/]\n")
    return 0
