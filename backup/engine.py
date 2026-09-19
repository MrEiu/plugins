"""
Backup Plugin Engine: GitKeep integration, binary resolution, and interactive restoration.
All comments and docstrings are in English.
"""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple

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

RESTORE_PICKER_STYLE = Style.from_dict({
    "restore.header": "bold #00f0ff",
    "restore.cursor": "bold #10b981",
    "restore.item_selected": "bold #ffffff bg:#334155",
    "restore.item_unselected": "#cbd5e1",
    "restore.hash": "bold #38bdf8",
    "restore.time": "#fbbf24",
    "restore.desc": "dim #94a3b8",
    "restore.footer": "dim #94a3b8",
    "restore.footer_key": "bold #38bdf8",
})


def format_relative_time(date_str: str) -> str:
    """Friendly formatting for ISO / git date string."""
    try:
        from datetime import datetime, timezone
        # Parse Git date format e.g. "2026-09-19 15:46:36 +0800"
        dt = datetime.strptime(date_str[:19], "%Y-%m-%d %H:%M:%S")
        now = datetime.now()
        diff_sec = int((now - dt).total_seconds())
        if diff_sec < 60:
            return "just now"
        if diff_sec < 3600:
            return f"{diff_sec // 60}m ago"
        if diff_sec < 86400:
            return f"{diff_sec // 3600}h ago"
        if diff_sec < 604800:
            return f"{diff_sec // 86400}d ago"
        return date_str[:16]
    except Exception:
        return date_str[:16] if len(date_str) >= 16 else date_str


def resolve_bk_command(cwd: Optional[Path] = None) -> Optional[List[str]]:
    """
    Locates the GitKeep executable with adaptive resolution:
    1. System PATH ('bk', 'backup', 'gitkeep')
    2. Global npm/pnpm/bun/yarn bin paths (AppData/Roaming/npm, pnpm, .bun/bin)
    3. Workspace or Desktop compiled binary (gitkeep/dist/bk.exe)
    4. Node.js runner with local cli.js (node gitkeep/bin/cli.js)
    """
    current_dir = cwd or Path.cwd()
    repo_root = Path(__file__).resolve().parent.parent.parent
    user_home = Path(os.environ.get("USERPROFILE" if sys.platform == "win32" else "HOME", Path.home()))
    is_win = sys.platform == "win32"

    # 1. Check system PATH
    for name in ["bk", "backup", "gitkeep"]:
        found = shutil.which(name)
        if found:
            return [found]

    # 2. Check Global npm, pnpm, bun, yarn bin paths
    if is_win:
        npm_candidates = [
            user_home / "AppData" / "Roaming" / "npm" / "bk.cmd",
            user_home / "AppData" / "Roaming" / "npm" / "backup.cmd",
            user_home / "AppData" / "Roaming" / "npm" / "gitkeep.cmd",
            user_home / "AppData" / "Local" / "pnpm" / "bk.cmd",
            user_home / "AppData" / "Local" / "pnpm" / "backup.cmd",
            user_home / ".bun" / "bin" / "bk.exe",
            user_home / ".bun" / "bin" / "bk",
            user_home / "AppData" / "Local" / "Yarn" / "bin" / "bk.cmd",
            user_home / "scoop" / "shims" / "bk.exe",
            user_home / "scoop" / "shims" / "bk.cmd",
        ]
    else:
        npm_candidates = [
            user_home / ".npm-global" / "bin" / "bk",
            user_home / ".npm-global" / "bin" / "backup",
            user_home / ".local" / "bin" / "bk",
            user_home / ".bun" / "bin" / "bk",
            Path("/usr/local/bin/bk"),
            Path("/usr/bin/bk"),
        ]

    for cand in npm_candidates:
        if cand.is_file():
            return [str(cand)]

    # 3. Candidate compiled binary paths (workspace, Desktop, etc.)
    candidate_exes = [
        repo_root / "gitkeep" / "dist" / "bk.exe",
        repo_root / "gitkeep" / "dist" / "bk",
        current_dir / "gitkeep" / "dist" / "bk.exe",
        current_dir / "gitkeep" / "dist" / "bk",
        Path("C:/Users/meru6/Desktop/gitkeep/dist/bk.exe"),
        user_home / "Desktop" / "gitkeep" / "dist" / "bk.exe",
    ]

    for candidate in candidate_exes:
        if candidate.is_file():
            return [str(candidate)]

    # 4. Node.js fallback with cli.js
    node_bin = shutil.which("node")
    if node_bin:
        candidate_scripts = [
            repo_root / "gitkeep" / "bin" / "cli.js",
            current_dir / "gitkeep" / "bin" / "cli.js",
            Path("C:/Users/meru6/Desktop/gitkeep/bin/cli.js"),
            user_home / "Desktop" / "gitkeep" / "bin" / "cli.js",
        ]
        for script in candidate_scripts:
            if script.is_file():
                return [node_bin, str(script)]

    return None


def get_backup_history(
    cwd: Optional[Path] = None,
    limit: int = 30,
) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
    """
    Fetches backup history via 'bk log --json -n <limit>'.
    Returns (commits_list, error_message).
    """
    cmd_prefix = resolve_bk_command(cwd)
    if not cmd_prefix:
        return None, "GitKeep executable (bk) not found."

    target_dir = cwd or Path.cwd()
    cmd = cmd_prefix + ["log", "--json", "-n", str(limit)]

    try:
        res = subprocess.run(
            cmd,
            cwd=str(target_dir),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if res.returncode != 0:
            err = res.stderr.strip() or res.stdout.strip() or "Failed to retrieve history."
            return None, err

        data = json.loads(res.stdout)
        commits = data.get("commits", [])
        return commits, None
    except json.JSONDecodeError:
        return None, "Failed to parse backup history JSON output."
    except Exception as e:
        return None, f"Error querying backup history: {e}"


def select_backup_version_interactive(commits: List[Dict[str, Any]]) -> Optional[str]:
    """
    Presents an interactive prompt_toolkit arrow-key picker for snapshot versions.
    Keys: [Up/Down] to navigate, [Enter] to restore, [Esc] to cancel.
    Returns selected shortHash, or None if cancelled.
    """
    if not commits:
        return None

    if not sys.stdin.isatty():
        # Headless fallback: return the latest snapshot
        return commits[0].get("shortHash") or commits[0].get("hash")

    selected_idx = 0

    def get_tokens() -> List[Tuple[str, str]]:
        tokens: List[Tuple[str, str]] = [
            ("class:restore.header", "\n📦 Select Historical Snapshot to Restore:\n"),
        ]

        # Display up to 12 items with scroll window if necessary
        window_size = 12
        start_idx = max(0, min(selected_idx - window_size // 2, len(commits) - window_size))
        end_idx = min(len(commits), start_idx + window_size)

        for idx in range(start_idx, end_idx):
            item = commits[idx]
            is_selected = (idx == selected_idx)
            short_h = item.get("shortHash", item.get("hash", "")[:7])
            rel_time = format_relative_time(item.get("date", "")).ljust(12)
            msg = item.get("message", "").strip()

            if is_selected:
                tokens.append(("class:restore.cursor", " ❯ "))
                tokens.append(("class:restore.item_selected", f" {short_h}  {rel_time}  {msg} \n"))
            else:
                tokens.append(("", "   "))
                tokens.append(("class:restore.hash", f"{short_h}"))
                tokens.append(("class:restore.time", f"  {rel_time}  "))
                tokens.append(("class:restore.desc", f"{msg}\n"))

        tokens.extend([
            ("class:restore.footer", "\n "),
            ("class:restore.footer_key", "[↑/↓]"),
            ("class:restore.footer", " Navigate · "),
            ("class:restore.footer_key", "[Enter]"),
            ("class:restore.footer", " Confirm Restore · "),
            ("class:restore.footer_key", "[Esc]"),
            ("class:restore.footer", " Cancel\n"),
        ])
        return tokens

    kb = KeyBindings()

    @kb.add("up")
    def _up(event: Any) -> None:
        nonlocal selected_idx
        selected_idx = (selected_idx - 1) % len(commits)
        event.app.invalidate()

    @kb.add("down")
    def _down(event: Any) -> None:
        nonlocal selected_idx
        selected_idx = (selected_idx + 1) % len(commits)
        event.app.invalidate()

    @kb.add("enter")
    def _enter(event: Any) -> None:
        chosen = commits[selected_idx]
        event.app.exit(result=chosen.get("shortHash") or chosen.get("hash"))

    @kb.add("escape")
    @kb.add("c-c")
    def _cancel(event: Any) -> None:
        event.app.exit(result=None)

    try:
        app = Application(
            layout=Layout(Window(FormattedTextControl(get_tokens))),
            key_bindings=kb,
            style=RESTORE_PICKER_STYLE,
            full_screen=False,
            output=get_safe_output(),
        )
        return app.run()
    except Exception:
        return None


def run_bk_passthrough(args: List[str], cwd: Optional[Path] = None, con: Optional[Console] = None) -> int:
    """
    Directly runs GitKeep CLI command with terminal passthrough.
    """
    console = con or Console(legacy_windows=False)
    cmd_prefix = resolve_bk_command(cwd)
    if not cmd_prefix:
        try:
            from .install import auto_install, print_installation_guide
        except ImportError:
            from plugins.backup.install import auto_install, print_installation_guide

        console.print("[yellow]GitKeep CLI engine ('bk') is not installed or not in PATH.[/yellow]")
        console.print("[dim]Attempting automatic installation of 'gitkeep-cli' via package manager...[/dim]\n")
        installed = auto_install(console)
        if installed:
            cmd_prefix = resolve_bk_command(cwd)
        if not cmd_prefix:
            print_installation_guide(console)
            return 1

    cmd = cmd_prefix + args
    try:
        res = subprocess.run(cmd, cwd=str(cwd or Path.cwd()))
        return res.returncode
    except KeyboardInterrupt:
        return 130
    except Exception as e:
        console.print(f"[bold red]Execution error:[/bold red] {e}")
        return 1
