"""
Alias Plugin for Kapsel.
Provides multi-terminal and cross-platform command mapping (e.g. Linux-first aliases to PowerShell/CMD/Unix).
Translates commands via Kapsel's FILTER_COMMAND hook and provides 'kps alias' management.
All comments and descriptions are in English.
"""

import json
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

from rich.console import Console
from rich.table import Table

from kapsel.core.plugin.base import KapselPlugin, PluginManifest
from kapsel.core.plugin.context import PluginContext
from kapsel.core.plugin.hooks import HookType
from kapsel.ui.banner import ensure_utf8_io

from .defaults import DEFAULT_MAPPINGS

ensure_utf8_io()


def _inject_args(template: str, args: str) -> str:
    """Safely injects command arguments into a template placeholder or appends them."""
    args_clean = args.strip()
    if "{{args}}" in template:
        if args_clean:
            res = template.replace("{{args}}", args_clean)
        else:
            res = template.replace("{{args}}", "").strip()
    else:
        if args_clean:
            res = f"{template} {args_clean}"
        else:
            res = template

    # Normalize whitespace
    return re.sub(r"\s+", " ", res).strip()


class AliasPlugin(KapselPlugin):
    """
    Cross-platform command alias translation plugin for Kapsel.
    Maps Linux-first universal commands to host shell native commands.
    """

    manifest = PluginManifest(
        id="alias",
        name="Alias",
        version="0.1.0",
        description="Multi-terminal command mapping translating universal aliases to host shell commands.",
        author="Kapsel Team",
        homepage="https://github.com/MrEiu/plugins/tree/master/alias",
        min_kapsel_version="0.1.0",
        tags=["alias", "mapping", "terminal", "cross-platform"],
    )

    def __init__(self) -> None:
        super().__init__()
        self.context: Optional[PluginContext] = None
        self.mappings: List[Dict[str, Any]] = []
        self.current_shell: str = "pwsh" if sys.platform == "win32" else "unix"

    def on_load(self, context: PluginContext) -> None:
        self.context = context
        # Detect active host shell from environment
        shell_name = getattr(context.environment, "current_shell", None)
        if shell_name:
            self.current_shell = shell_name.lower()

        # Load persistent mappings from plugin data directory
        self._load_mappings()

        # 1. Register Pre-execution command filter hook
        context.register_hook(HookType.FILTER_COMMAND, self.filter_command)

        # 2. Register management command: 'kps alias'
        context.register_kps_command(
            name="alias",
            handler=self.handle_alias,
            help_text="Manage and inspect cross-platform command aliases and mappings",
            usage="kps alias [list|test|add|remove|reset] [options]",
            scope="feature",
        )

    def _get_mappings_file(self) -> Path:
        assert self.context is not None
        return self.context.plugin_data_dir / "mappings.json"

    def _load_mappings(self) -> None:
        """Loads mappings from disk, falling back to defaults if uninitialized."""
        mappings_file = self._get_mappings_file()
        if mappings_file.exists():
            try:
                with open(mappings_file, "r", encoding="utf-8") as f:
                    self.mappings = json.load(f)
                return
            except Exception:
                pass

        # Seed defaults
        self.mappings = list(DEFAULT_MAPPINGS)
        self._save_mappings()

    def _save_mappings(self) -> None:
        """Saves current mappings to disk."""
        mappings_file = self._get_mappings_file()
        try:
            with open(mappings_file, "w", encoding="utf-8") as f:
                json.dump(self.mappings, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def _get_template_for_entry(self, entry: Dict[str, Any], shell: str) -> Optional[str]:
        templates = entry.get("templates", {})
        if shell in templates:
            return templates[shell]
        if shell == "pwsh" and "powershell" in templates:
            return templates["powershell"]
        if shell == "powershell" and "pwsh" in templates:
            return templates["pwsh"]
        if "unix" in templates:
            return templates["unix"]
        return next(iter(templates.values()), None)

    def filter_command(self, raw_command: str) -> Tuple[bool, str]:
        """
        Translates 'kps <alias>' into native host shell command.
        Example: 'kps rm -rf node_modules' -> 'Remove-Item -Recurse -Force node_modules'
        """
        stripped = raw_command.strip()
        if not (stripped.startswith("kps ") or stripped == "kps"):
            return False, raw_command

        body = stripped[4:].strip()
        if not body:
            return False, raw_command

        # Do not intercept existing core or plugin commands
        reserved_cmds = {"install", "rec", "sync", "update", "search", "alias", "help", "status"}
        first_token = body.split()[0].lower()
        if first_token in reserved_cmds:
            return False, raw_command

        # Sort mappings by descending alias length for longest-prefix match (e.g. 'rm -rf' before 'rm')
        sorted_mappings = sorted(self.mappings, key=lambda m: len(m["alias"]), reverse=True)

        for m in sorted_mappings:
            alias = m["alias"]
            if body == alias:
                template = self._get_template_for_entry(m, self.current_shell)
                if template:
                    return True, _inject_args(template, "")
            elif body.startswith(alias + " "):
                raw_args = body[len(alias) + 1:].strip()
                template = self._get_template_for_entry(m, self.current_shell)
                if template:
                    return True, _inject_args(template, raw_args)

        return False, raw_command

    def handle_alias(self, args: List[str], console: Optional[Console] = None) -> int:
        """Handles 'kps alias' management subcommands."""
        con = console or Console(legacy_windows=False)

        if not args or args[0].lower() in ("list", "ls"):
            return self._show_list(con)

        subcmd = args[0].lower()
        sub_args = args[1:]

        if subcmd == "test":
            if not sub_args:
                con.print("[bold #f43f5e]Error:[/] Please provide a command to test translation.")
                con.print("[dim]Usage: kps alias test <command...>[/]\n")
                return 1
            test_line = "kps " + " ".join(sub_args)
            is_handled, translated = self.filter_command(test_line)
            con.print(f"\n[bold #00f0ff]● Alias Translation Test[/]")
            con.print(f"  [dim]Input Command:[/]      [white]{test_line}[/]")
            con.print(f"  [dim]Active Shell:[/]       [white]{self.current_shell}[/]")
            if is_handled:
                con.print(f"  [dim]Translated Output:[/]  [bold #10b981]{translated}[/]\n")
            else:
                con.print(f"  [dim]Translated Output:[/]  [yellow]No mapping found (pass-through)[/]\n")
            return 0

        elif subcmd == "add":
            if len(sub_args) < 2:
                con.print("[bold #f43f5e]Error:[/] Usage: kps alias add <alias> <template>")
                con.print("[dim]Example: kps alias add 'git-clean' 'git clean -fdx'[/]\n")
                return 1
            new_alias = sub_args[0]
            new_template = " ".join(sub_args[1:])
            # Update or append
            for m in self.mappings:
                if m["alias"] == new_alias:
                    m["templates"][self.current_shell] = new_template
                    self._save_mappings()
                    con.print(f"[bold #10b981]✔ Updated alias '[#00f0ff]{new_alias}[/]' -> '[#a855f7]{new_template}[/]'.[/]")
                    return 0

            self.mappings.append({
                "alias": new_alias,
                "desc": f"Custom user alias for {new_alias}",
                "templates": {self.current_shell: new_template, "unix": new_template},
            })
            self._save_mappings()
            con.print(f"[bold #10b981]✔ Added alias '[#00f0ff]{new_alias}[/]' -> '[#a855f7]{new_template}[/]'.[/]")
            return 0

        elif subcmd in ("remove", "rm", "delete"):
            if not sub_args:
                con.print("[bold #f43f5e]Error:[/] Please specify the alias to remove.")
                return 1
            target_alias = sub_args[0]
            initial_len = len(self.mappings)
            self.mappings = [m for m in self.mappings if m["alias"] != target_alias]
            if len(self.mappings) < initial_len:
                self._save_mappings()
                con.print(f"[bold #10b981]✔ Successfully removed alias '[#00f0ff]{target_alias}[/]'.[/]")
                return 0
            else:
                con.print(f"[yellow]Alias '{target_alias}' not found in mappings.[/]")
                return 1

        elif subcmd == "reset":
            self.mappings = list(DEFAULT_MAPPINGS)
            self._save_mappings()
            con.print("[bold #10b981]✔ Reset all alias mappings to baseline defaults.[/]")
            return 0

        elif subcmd in ("-h", "--help", "help"):
            con.print("\n[bold #00f0ff]● Kapsel Alias Plugin (Command Mapping)[/]")
            con.print("[dim]Translates universal commands to host native shell commands via 'kps <alias>'.[/]\n")
            con.print("[bold white]Usage:[/]")
            con.print("  [bold #a855f7]kps alias[/] (or list)              List active aliases for current shell")
            con.print("  [bold #a855f7]kps alias test <command...>[/]      Preview translated command without running")
            con.print("  [bold #a855f7]kps alias add <alias> <template>[/] Add or update an alias mapping")
            con.print("  [bold #a855f7]kps alias remove <alias>[/]         Remove an alias mapping")
            con.print("  [bold #a855f7]kps alias reset[/]                  Reset all mappings to default baseline\n")
            return 0

        else:
            con.print(f"[bold #f43f5e]Unknown subcommand '{subcmd}'.[/] Use 'kps alias --help' for usage.")
            return 1

    def _show_list(self, con: Console) -> int:
        table = Table(
            title=f"● Kapsel Active Mappings ({self.current_shell.upper()})",
            title_style="bold #00f0ff",
            border_style="#0891b2",
            header_style="bold white",
        )
        table.add_column("Universal Alias", style="bold #a855f7", width=18)
        table.add_column("Host Native Template", style="#00f0ff", min_width=35)
        table.add_column("Description", style="dim white")

        for m in self.mappings:
            alias = m["alias"]
            template = self._get_template_for_entry(m, self.current_shell) or "[dim]N/A[/]"
            desc = m.get("desc", "")
            table.add_row(alias, template, desc)

        con.print()
        con.print(table)
        con.print(f"[dim]Total: {len(self.mappings)} mappings loaded. Run with 'kps <alias>' (e.g. kps rm -rf dir).[/]\n")
        return 0
