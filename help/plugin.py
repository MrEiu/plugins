"""
Help (Fast Command Cheat Sheets) Plugin for Kapsel.
Bridges 'tealdeer' (a blazing fast implementation of tldr) to provide practical CLI cheat sheets.
Exposes functional commands under the 'kps help' namespace.
Distinct from 'kapsel help', which serves Kapsel shell system management.
All comments and descriptions are in English.
"""

from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional

from rich.console import Console

from kapsel.core.plugin.base import KapselPlugin, PluginManifest
from kapsel.core.plugin.context import PluginContext
from kapsel.core.plugin.hooks import HookType
from kapsel.storage.config import get_kapsel_dir
from kapsel.ui.banner import ensure_utf8_io

ensure_utf8_io()


def _resolve_tldr_executable() -> Optional[str]:
    """
    Locates the tealdeer / tldr executable:
    1. System PATH (tldr / tealdeer)
    2. Local Kapsel bin directory (~/.kapsel/bin/tldr.exe or tldr)
    """
    # 1. System PATH
    for name in ("tldr", "tealdeer"):
        p = shutil.which(name)
        if p:
            return p

    # 2. Local Kapsel bin directory (~/.kapsel/bin)
    bin_dir = get_kapsel_dir() / "bin"
    is_win = sys.platform == "win32"
    for name in ("tldr.exe" if is_win else "tldr", "tealdeer.exe" if is_win else "tealdeer"):
        local_bin = bin_dir / name
        if local_bin.exists():
            return str(local_bin)

    return None


def _run_tldr_command(args: List[str], console: Optional[Console] = None) -> int:
    """Executes a tealdeer command, streaming output directly to the terminal."""
    con = console or Console(legacy_windows=False)
    tldr_bin = _resolve_tldr_executable()

    if not tldr_bin:
        con.print("[bold #f43f5e]Error:[/] [white]tealdeer (tldr CLI client) is not installed.[/]")
        con.print("[dim]To install tealdeer automatically, run:[/] [bold #00f0ff]kapsel add help[/]\n")
        return 1

    try:
        proc = subprocess.run([tldr_bin] + args)
        return proc.returncode
    except KeyboardInterrupt:
        con.print("\n[dim]Aborted.[/]")
        return 130
    except Exception as e:
        con.print(f"[bold #f43f5e]Failed to execute tealdeer:[/] {e}")
        return 1


class HelpPlugin(KapselPlugin):
    """
    Kapsel 'help' feature plugin integrating tealdeer (tldr).
    Provides rapid command cheat sheets ('kps help tar', 'kps help curl', etc.).
    """

    manifest = PluginManifest(
        id="help",
        name="Help",
        version="0.1.0",
        description="Fast command cheat sheets and quick lookup powered by tealdeer (tldr).",
        author="Kapsel Team",
        homepage="https://github.com/MrEiu/plugins/tree/master/help",
        min_kapsel_version="0.1.0",
        dependencies=["tealdeer"],
        tags=["help", "cheatsheet", "tldr", "tealdeer", "docs", "tools"],
    )

    def __init__(self) -> None:
        super().__init__()
        self._cached_page_names: Optional[List[str]] = None

    def on_load(self, context: PluginContext) -> None:
        """Registers the 'help' functional command under 'kps' scope and completion hook."""
        context.register_kps_command(
            name="help",
            handler=self.handle_help,
            help_text="Fast command cheat sheets powered by tealdeer (tldr)",
            usage="kps help <command...> [options]",
            subcommands={
                "--update": "Update local tldr cheat sheet cache",
                "--list": "List all available command cheat sheets",
                "--platform": "Select target platform (linux, macos, windows, common)",
                "--raw": "Display raw markdown page without rendering",
                "--clear-cache": "Clear local cheat sheet cache",
            },
            scope="feature",
        )

        # Register completion hook for command names
        context.register_hook(HookType.PROVIDE_COMPLETIONS, self.provide_completions)

    def handle_help(self, args: List[str], console: Optional[Console] = None) -> int:
        """
        Dispatches 'kps help' queries:
        - 'kps help' (bare)          -> Shows guide and notes distinction from 'kapsel help'
        - 'kps help <command...>'    -> Queries tealdeer for command examples (e.g. 'kps help tar')
        - 'kps help -u' / '--update' -> Updates local page cache
        - 'kps help -l' / '--list'   -> Lists all available command pages
        """
        con = console or Console(legacy_windows=False)

        # If bare 'kapsel help' or 'kps help' without arguments, display unified Kapsel manual
        if not args:
            from kapsel.completion.kps.builtins.help import handle_help as handle_system_help
            return handle_system_help([], con)

        if args in (["-h"], ["--help"]):
            con.print("\n[bold #00f0ff]📖 Kapsel Help Plugin (Fast Command Cheat Sheets)[/]")
            con.print("[dim]Powered by 'tealdeer' (https://github.com/tealdeer-rs/tealdeer)[/]\n")
            con.print("[bold white]Usage:[/]")
            con.print("  [bold #a855f7]kps help <command...>[/]       Lookup cheat sheet for a command (e.g. 'kps help tar', 'kps help git commit')")
            con.print("  [bold #a855f7]kps help --update / -u[/]      Update local tldr page cache from GitHub")
            con.print("  [bold #a855f7]kps help --list / -l[/]        List all available command pages in cache")
            con.print("  [bold #a855f7]kps help -p <os> <cmd>[/]      Specify operating system (linux, macos, windows, common)")
            con.print("  [bold #a855f7]kps help --raw <cmd>[/]         Display raw markdown content without rendering\n")
            return 0

        # Execute tealdeer with all forwarded arguments
        return _run_tldr_command(args, con)

    def provide_completions(self, text_before_cursor: str) -> List[Dict[str, Any]]:
        """
        Provides dynamic auto-completions for command names when typing 'kps help <prefix>'.
        Example: 'kps help ta' -> ['tar', 'tarsnap', ...]
        """
        stripped = text_before_cursor.lstrip()
        prefix_tag = "kps help"
        if not stripped.startswith(prefix_tag):
            return []

        after_cmd = stripped[len(prefix_tag):]
        if not after_cmd.startswith(" "):
            return []

        query = after_cmd.strip()
        if query.startswith("-"):
            # Flags are already handled by subcommands registry
            return []

        pages = self._get_cached_pages()
        if not pages:
            return []

        q_lower = query.lower()
        candidates: List[Dict[str, Any]] = []

        for p_name in pages:
            if p_name.lower().startswith(q_lower):
                candidates.append({
                    "text": p_name,
                    "display": p_name,
                    "display_meta": "📖 tldr cheat sheet",
                    "start_position": -len(query),
                })
                if len(candidates) >= 15:
                    break

        return candidates

    def _get_cached_pages(self) -> List[str]:
        """Lazy loads and caches available tldr command names for fast auto-completion."""
        if self._cached_page_names is not None:
            return self._cached_page_names

        tldr_bin = _resolve_tldr_executable()
        if not tldr_bin:
            return []

        try:
            res = subprocess.run(
                [tldr_bin, "--list"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=2.0,
            )
            if res.returncode == 0 and res.stdout:
                self._cached_page_names = [line.strip() for line in res.stdout.splitlines() if line.strip()]
                return self._cached_page_names
        except Exception:
            pass

        return []
