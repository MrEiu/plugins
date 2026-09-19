"""
Commit Plugin for Kapsel.
Offline rule-based Conventional Commit generator & interactive Git commit manager.
All comments and docstrings are in English.
"""

from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from kapsel.core.plugin.base import KapselPlugin, PluginManifest
from kapsel.core.plugin.context import PluginContext
from kapsel.core.plugin.hooks import HookType

try:
    from .engine import (
        is_git_repository,
        deduce_commit_message,
        select_commit_type_interactive,
        copy_to_clipboard,
        execute_git_commit,
    )
except ImportError:
    from plugins.commit.engine import (
        is_git_repository,
        deduce_commit_message,
        select_commit_type_interactive,
        copy_to_clipboard,
        execute_git_commit,
    )


class CommitPlugin(KapselPlugin):
    """
    Kapsel Commit Plugin: Offline rule-based Conventional Commit deduction
    and interactive git commit engine. Zero network, zero LLM dependency, 100% deterministic.
    """

    manifest = PluginManifest(
        id="commit",
        name="Commit",
        version="0.1.0",
        description="Offline rule-based Conventional Commit deduction and interactive git commit manager.",
        author="Kapsel Team",
        homepage="https://github.com/MrEiu/plugins/tree/master/commit",
        min_kapsel_version="0.1.0",
        tags=["git", "commit", "conventional-commits", "vcs", "automation", "offline"],
    )

    def __init__(self) -> None:
        super().__init__()
        self.context: Optional[PluginContext] = None

    def on_load(self, context: PluginContext) -> None:
        self.context = context

        # 1. Pre-execution filter: intercepts 'commit' and 'kps commit'
        context.register_hook(HookType.FILTER_COMMAND, self.filter_command)

        # 2. Dynamic autocompletion for commit options
        context.register_hook(HookType.PROVIDE_COMPLETIONS, self.provide_completions)

        # 3. Register functional command under kps namespace
        context.register_kps_command(
            name="commit",
            handler=self.handle_commit,
            help_text="Generate Conventional Commit from Git status and commit interactively",
            usage="kps commit [options] [-m <message>]",
            subcommands={
                "-m": "Specify commit message directly",
                "-t": "Override commit type (feat, fix, docs, refactor, perf, test, chore)",
                "-s": "Override commit scope",
                "-a": "Stage all changes (git add -A) before committing",
                "-d": "Dry-run: print deduced commit message without executing git commit",
            },
            scope="feature",
        )

    def filter_command(self, raw_command: str) -> Tuple[bool, str]:
        """
        Intercepts:
        1. 'commit [args...]' -> interactive commit workflow
        2. 'kps commit [args...]' -> interactive commit workflow
        """
        stripped = raw_command.strip()
        if not stripped:
            return False, raw_command

        tokens = stripped.split()
        prefix = tokens[0].lower()

        if prefix == "commit":
            con = Console(legacy_windows=False)
            self.handle_commit(tokens[1:], con)
            return True, ""

        if stripped.lower().startswith("kps commit"):
            con = Console(legacy_windows=False)
            self.handle_commit(tokens[2:], con)
            return True, ""

        return False, raw_command

    def provide_completions(self, text_before_cursor: str) -> List[dict]:
        """Provides options autocomplete for commit command."""
        stripped = text_before_cursor.lstrip()
        matched_prefix = None
        for p in ("kps commit ", "commit "):
            if stripped.startswith(p):
                matched_prefix = p
                break

        if not matched_prefix:
            return []

        remainder = stripped[len(matched_prefix):]
        options = [
            {"text": "-m", "display": "-m <msg>", "display_meta": "Custom message"},
            {"text": "-t", "display": "-t <type>", "display_meta": "Set type (feat/fix/docs...)"},
            {"text": "-s", "display": "-s <scope>", "display_meta": "Set scope"},
            {"text": "-d", "display": "-d, --dry-run", "display_meta": "Print deduced message only"},
            {"text": "-a", "display": "-a, --all", "display_meta": "Stage all changes"},
        ]

        if remainder.startswith("-"):
            return [opt for opt in options if opt["text"].startswith(remainder)]
        return options

    def handle_commit(self, args: List[str], console: Optional[Console] = None) -> int:
        """Main dispatcher for commit requests."""
        con = console or Console(legacy_windows=False)

        if not is_git_repository():
            con.print("[bold #f43f5e]Error:[/] Current directory is not a Git repository.\n")
            return 1

        # Parse command-line flags
        custom_message: Optional[str] = None
        custom_type: Optional[str] = None
        custom_scope: Optional[str] = None
        dry_run: bool = False
        stage_all: bool = True

        idx = 0
        while idx < len(args):
            arg = args[idx]
            if arg in ("-m", "--message") and idx + 1 < len(args):
                custom_message = args[idx + 1]
                idx += 2
            elif arg in ("-t", "--type") and idx + 1 < len(args):
                custom_type = args[idx + 1].lower()
                idx += 2
            elif arg in ("-s", "--scope") and idx + 1 < len(args):
                custom_scope = args[idx + 1].strip()
                idx += 2
            elif arg in ("-d", "--dry-run"):
                dry_run = True
                idx += 1
            elif arg in ("-h", "--help", "help"):
                self._render_help(con)
                return 0
            else:
                idx += 1

        # 1. Direct message pass-through if -m is provided
        if custom_message:
            if dry_run:
                con.print(f"[bold #00f0ff]Dry-run:[/] {custom_message}\n")
                return 0
            return execute_git_commit(custom_message, stage_all=stage_all, con=con)

        # 2. Offline rule-based deduction
        deduced_msg, files, meta = deduce_commit_message()
        if not files:
            con.print("\n[bold #10b981]✔ Working tree clean. Nothing to commit.[/]\n")
            return 0

        # Apply overrides if provided via flags
        current_type = custom_type or meta["type"]
        current_scope = custom_scope if custom_scope is not None else meta["scope"]
        current_subject = meta["subject"]

        def _format_msg(t: str, sc: str, sub: str) -> str:
            return f"{t}({sc}): {sub}" if sc else f"{t}: {sub}"

        active_msg = _format_msg(current_type, current_scope, current_subject)

        if dry_run:
            con.print(f"[bold #00f0ff]Auto-Deducted Message:[/] {active_msg}\n")
            return 0

        # 3. Interactive Workflow Loop
        while True:
            con.print(f"\n[bold #00f0ff]📦 Git Changes Detected:[/] [white]{len(files)} file(s)[/]")

            # Render compact changes list (up to 8 files)
            for f in files[:8]:
                status_icon = "📝 M" if f["status"] == "M" else ("✨ A" if f["status"] in ("A", "?") else "🗑️ D")
                staged_badge = "[#10b981]staged[/]" if f["is_staged"] else "[dim]unstaged[/]"
                con.print(f"  [dim]{status_icon}[/] [white]{f['path']}[/] [dim]({staged_badge})[/]")
            if len(files) > 8:
                con.print(f"  [dim]... and {len(files) - 8} more file(s)[/]")

            con.print(f"\n[bold #00f0ff]💡 Auto-Deducted Commit Message:[/] [dim](rule-based offline)[/]")
            con.print(Panel(f"[bold #10b981]{active_msg}[/]", border_style="#00f0ff", expand=False))

            con.print("[dim]Actions:[/] [bold green][Enter][/] Commit  [bold cyan][e][/] Edit  [bold magenta][t][/] Change Type  [bold yellow][c][/] Copy  [bold red][q / Esc][/] Cancel")

            try:
                choice = input("❯ ").strip().lower()
                if choice in ("", "y", "yes"):
                    return execute_git_commit(active_msg, stage_all=stage_all, con=con)
                elif choice in ("e", "edit"):
                    con.print(f"[dim]Press Enter to accept current message, or edit below:[/]")
                    user_input = input(f"❯ {active_msg} ➔ ").strip()
                    if user_input:
                        active_msg = user_input
                    return execute_git_commit(active_msg, stage_all=stage_all, con=con)
                elif choice in ("t", "type"):
                    new_type = select_commit_type_interactive(current_type)
                    if new_type:
                        current_type = new_type
                        active_msg = _format_msg(current_type, current_scope, current_subject)
                    continue
                elif choice in ("c", "copy"):
                    copy_to_clipboard(active_msg)
                    con.print("[bold #10b981]✔ Commit message copied to clipboard![/]\n")
                    return 0
                else:
                    con.print("[dim]Commit cancelled.[/]\n")
                    return 0
            except (KeyboardInterrupt, EOFError):
                con.print("\n[dim]Commit cancelled.[/]\n")
                return 0

    def _render_help(self, con: Console) -> None:
        """Renders usage and command options."""
        con.print("\n[bold #00f0ff]Kapsel Commit (kps commit) - Offline Rule-Based Conventional Commit Engine[/]")
        con.print("[dim]Automatically analyzes Git changes and deduces standardized Conventional Commits with zero network or AI dependency.[/]\n")
        con.print("[bold white]Usage:[/]")
        con.print("  [#38bdf8]commit[/]                   Analyze Git status and commit interactively")
        con.print("  [#38bdf8]commit -m <message>[/]     Directly commit with custom message")
        con.print("  [#38bdf8]commit -t <type>[/]        Override commit type (feat, fix, docs, etc.)")
        con.print("  [#38bdf8]commit -d[/]                Dry-run: print deduced message only\n")


Plugin = CommitPlugin
