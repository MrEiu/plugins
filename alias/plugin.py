"""
Alias Plugin for Kapsel.
Provides multi-terminal and cross-platform command mapping (e.g. Linux-first aliases to PowerShell/CMD/Unix).
Translates commands via Kapsel's FILTER_COMMAND hook and provides 'kps alias' management.
Includes progressive modern CLI tool enhancement (eza, bat, ripgrep, fd, procs, etc.) and 'kps alias ultra'.
All comments and descriptions are in English.
"""

import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from kapsel.core.plugin.base import KapselPlugin, PluginManifest
from kapsel.core.plugin.context import PluginContext
from kapsel.core.plugin.hooks import HookType
from kapsel.ui.banner import ensure_utf8_io

from .defaults import DEFAULT_MAPPINGS, ULTRA_TOOLS

ensure_utf8_io()


def _inject_args(template: str, args: str) -> str:
    """Safely injects command arguments into a template placeholder or appends them without corrupting quoted whitespace."""
    tpl = template.strip()
    args_clean = args.strip()
    if "{{args}}" in tpl:
        if args_clean:
            return tpl.replace("{{args}}", args_clean).strip()
        else:
            return re.sub(r"\s+", " ", tpl.replace("{{args}}", "")).strip()
    else:
        if args_clean:
            return f"{tpl} {args_clean}"
        else:
            return tpl


def _split_pipeline(command: str) -> List[str]:
    """Splits a command line by pipe characters '|' while ignoring pipes inside quotes."""
    segments: List[str] = []
    current: List[str] = []
    in_single_quote = False
    in_double_quote = False
    escape = False

    for ch in command:
        if escape:
            current.append(ch)
            escape = False
            continue

        if ch == "\\":
            current.append(ch)
            escape = True
            continue

        if ch == "'" and not in_double_quote:
            in_single_quote = not in_single_quote
            current.append(ch)
        elif ch == '"' and not in_single_quote:
            in_double_quote = not in_double_quote
            current.append(ch)
        elif ch == "|" and not in_single_quote and not in_double_quote:
            segments.append("".join(current))
            current = []
        else:
            current.append(ch)

    segments.append("".join(current))
    return segments


class AliasPlugin(KapselPlugin):
    """
    Cross-platform command alias translation plugin for Kapsel.
    Maps Linux-first universal commands to host shell native commands and modern CLI tools.
    """

    manifest = PluginManifest(
        id="alias",
        name="Alias",
        version="0.2.5",
        description="Multi-terminal command mapping translating universal aliases to host shell commands.",
        author="Kapsel Team",
        homepage="https://github.com/MrEiu/plugins/tree/master/alias",
        min_kapsel_version="0.1.0",
        tags=["alias", "mapping", "terminal", "cross-platform", "ultra"],
    )

    def __init__(self) -> None:
        super().__init__()
        self.context: Optional[PluginContext] = None
        self.mappings: List[Dict[str, Any]] = []
        self.current_shell: str = "pwsh" if sys.platform == "win32" else "unix"

    def on_load(self, context: PluginContext) -> None:
        self.context = context
        # Detect active host shell from environment
        env = getattr(context, "environment", None)
        shell_name = getattr(env, "current_shell", None) if env else None
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
            help_text="Manage cross-platform command aliases, inspect mappings, or install ultra tools",
            usage="kps alias [list|add|remove|test|reset|ultra] [options]",
            scope="feature",
            subcommands={
                "list": "Display active mappings and ultra modern tools status",
                "add": "Add or update an alias (default current shell, or -p for multi-platform)",
                "remove": "Remove an alias or specific platform template",
                "test": "Preview command translation across shell platforms",
                "reset": "Reset all mappings to baseline defaults",
                "ultra": "One-click install modern high-performance CLI tools suite (eza, bat, rg, etc.)",
            },
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
                    data = json.load(f)
                    if isinstance(data, list) and data:
                        self.mappings = data
                        return
            except Exception:
                pass

        # Seed defaults
        self.mappings = [dict(m) for m in DEFAULT_MAPPINGS]
        self._save_mappings()

    def _save_mappings(self) -> None:
        """Saves current mappings to disk."""
        mappings_file = self._get_mappings_file()
        try:
            with open(mappings_file, "w", encoding="utf-8") as f:
                json.dump(self.mappings, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def _resolve_template_for_entry(self, entry: Dict[str, Any], shell: str) -> Optional[str]:
        """
        Resolves command template applying progressive enhancement:
        1. If a modern tool (e.g. bat, eza, rg) is specified and installed, use modern_template.
        2. Otherwise fallback to shell-specific or universal template.
        """
        # 1. Progressive modern tool check
        modern_tool = entry.get("modern_tool")
        modern_tpl = entry.get("modern_template")
        if modern_tool and modern_tpl:
            if shutil.which(modern_tool):
                return modern_tpl

        # 2. Host shell templates fallback
        templates = entry.get("templates", {})
        if shell in templates:
            return templates[shell]
        if shell == "pwsh" and "powershell" in templates:
            return templates["powershell"]
        if shell == "powershell" and "pwsh" in templates:
            return templates["pwsh"]
        if "universal" in templates:
            return templates["universal"]
        if "all" in templates:
            return templates["all"]
        if "unix" in templates and sys.platform != "win32":
            return templates["unix"]

        # Default fallback to first non-empty template
        for v in templates.values():
            if v:
                return v

        return None

    def _translate_single_command(self, raw_part: str) -> Tuple[bool, str]:
        """Translates a single command segment (without outer pipes)."""
        stripped = raw_part.strip()
        if not stripped:
            return False, raw_part

        # The 'kps' and 'kapsel' namespaces are strictly preserved
        if stripped == "kps" or stripped.startswith("kps "):
            return False, raw_part
        if stripped == "kapsel" or stripped.startswith("kapsel "):
            return False, raw_part

        # Sort mappings by descending alias length for longest-prefix match (e.g. 'rm -rf' before 'rm')
        sorted_mappings = sorted(self.mappings, key=lambda m: len(m.get("alias", "")), reverse=True)

        for m in sorted_mappings:
            alias = m.get("alias", "")
            if not alias:
                continue

            if stripped == alias:
                template = self._resolve_template_for_entry(m, self.current_shell)
                if template:
                    return True, _inject_args(template, "")
            elif stripped.startswith(alias + " "):
                raw_args = stripped[len(alias) + 1:].strip()
                template = self._resolve_template_for_entry(m, self.current_shell)
                if template:
                    return True, _inject_args(template, raw_args)

        return False, raw_part

    def filter_command(self, raw_command: str) -> Tuple[bool, str]:
        """
        Translates universal Linux-first aliases entered in the Kapsel interactive shell
        into native host shell commands (or modern CLI tools).
        Supports pipeline segmentation (splitting by '|').
        Note:
        - 'kps ...' and 'kapsel ...' commands are strictly preserved and never intercepted.
        - Direct interactive typing (e.g. 'rm -rf dir', 'cat file', 'll') is transparently translated.
        """
        try:
            stripped = raw_command.strip()
            if not stripped:
                return False, raw_command

            # The 'kps' and 'kapsel' namespaces are strictly preserved for tools and system management
            if stripped == "kps" or stripped.startswith("kps "):
                return False, raw_command
            if stripped == "kapsel" or stripped.startswith("kapsel "):
                return False, raw_command

            segments = _split_pipeline(stripped)
            if len(segments) <= 1:
                handled, translated = self._translate_single_command(stripped)
                if not handled:
                    return False, raw_command

                # "就相当于直接输入":
                # If the translated command is an internal Kapsel command (kps ..., kapsel ..., kp ...),
                # dispatch it in-process directly.
                trans_stripped = translated.strip()
                if (
                    trans_stripped in ("kps", "kapsel", "kp")
                    or trans_stripped.startswith("kps ")
                    or trans_stripped.startswith("kapsel ")
                    or trans_stripped.startswith("kp ")
                ):
                    try:
                        from kapsel.completion.kps.dispatcher import dispatch_kps
                        con = Console(legacy_windows=False)
                        dispatch_kps(trans_stripped, con)
                        return True, ""
                    except Exception:
                        pass

                return True, translated

            translated_segments: List[str] = []
            any_handled = False

            for seg in segments:
                handled, trans = self._translate_single_command(seg)
                if handled:
                    any_handled = True
                    translated_segments.append(trans)
                else:
                    translated_segments.append(seg.strip())

            if any_handled:
                return True, " | ".join(translated_segments)
            return False, raw_command
        except Exception:
            return False, raw_command

    def handle_alias(self, args: List[str], console: Optional[Console] = None) -> int:
        """Handles 'kps alias' management subcommands or interactive creation."""
        con = console or Console(legacy_windows=False)

        # 1. Detect bracket syntax in arguments, e.g. kps alias [help] [kps help]
        raw_args_line = " ".join(args).strip()
        bracket_matches = re.findall(r"\[(.*?)\]", raw_args_line)
        if len(bracket_matches) >= 2:
            return self._handle_bracket_add(bracket_matches, con)

        # 2. Interactive Mode: user simply typed 'kps alias' with NO arguments
        if not args:
            return self._handle_interactive_add(con)

        subcmd = args[0].lower()
        sub_args = args[1:]

        # Explicit list: 'kps alias list' or 'kps alias ls'
        if subcmd in ("list", "ls"):
            target_platform = None
            if sub_args and sub_args[0] not in ("-h", "--help"):
                target_platform = sub_args[0]
            return self._show_list(con, platform_filter=target_platform)

        # Explicit add: 'kps alias add ...'
        if subcmd == "add":
            raw_sub = " ".join(sub_args).strip()
            brackets = re.findall(r"\[(.*?)\]", raw_sub)
            if len(brackets) >= 2:
                return self._handle_bracket_add(brackets, con)
            return self._handle_add(sub_args, con)

        if subcmd == "ultra":
            return self._handle_ultra(sub_args, con)

        if subcmd == "test":
            return self._handle_test(sub_args, con)

        if subcmd in ("remove", "rm", "delete"):
            return self._handle_remove(sub_args, con)

        if subcmd == "reset":
            return self._handle_reset(sub_args, con)

        if subcmd in ("-h", "--help", "help"):
            return self._show_help(con)

        # Direct syntax without 'add' keyword: kps alias <alias> <template>
        if len(args) >= 2:
            return self._handle_add(args, con)

        con.print(f"[bold #f43f5e]Unknown subcommand '{subcmd}'.[/] Use 'kps alias --help' for usage.\n")
        return 1

    def _handle_bracket_add(self, brackets: List[str], con: Console) -> int:
        """
        Handles 1:1 verbatim mapping specified via brackets:
        kps alias [alias] [target] [optional_platform]
        Pure verbatim mapping without alteration.
        """
        alias_name = brackets[0].strip()
        target_template = brackets[1]  # Verbatim 1:1 mapping preserving exact user content
        platform_spec = brackets[2].strip().lower() if len(brackets) > 2 else self.current_shell

        if not alias_name or not target_template:
            con.print("[bold #f43f5e]Error:[/] Both alias and target command must not be empty.\n")
            return 1

        platforms = [p.strip() for p in platform_spec.split(",") if p.strip()]
        if "universal" in platforms or "all" in platforms:
            expanded_platforms = ["universal", "pwsh", "cmd", "unix", "powershell"]
        else:
            expanded_platforms = platforms

        updated = False
        for m in self.mappings:
            if m.get("alias") == alias_name:
                for p in expanded_platforms:
                    m.setdefault("templates", {})[p] = target_template
                updated = True
                break

        if not updated:
            new_entry = {
                "alias": alias_name,
                "desc": f"Alias for {alias_name}",
                "templates": {p: target_template for p in expanded_platforms},
            }
            self.mappings.append(new_entry)

        self._save_mappings()
        con.print(f"[bold #10b981]✔ Mapped:[/] [bold #00f0ff]{alias_name}[/] [dim]->[/] [bold #a855f7]{target_template}[/]\n")
        return 0

    def _handle_interactive_add(self, con: Console) -> int:
        """
        Interactive 2-step alias mapping:
        1. Prompt for trigger command/word (with alias & CLI tool autocompletion)
        2. Prompt for target command to map to (with full Carapace command autocompletion)
        Verbatim 1:1 mapping without modification.
        """
        con.print("\n[bold #00f0ff]⚡ Kapsel Alias · Command Mapping[/]")
        con.print("[dim]Define custom command mapping (Press Esc or Ctrl+C to cancel)[/]\n")

        try:
            from prompt_toolkit import prompt
            from prompt_toolkit.completion import Completer, Completion, ThreadedCompleter
            from prompt_toolkit.formatted_text import HTML
            from kapsel.completion.carapace_engine import CarapaceEngine
            from kapsel.completion.completer import DualStateCompleter
            from kapsel.ui.theme import PT_STYLE

            class _AliasTriggerCompleter(Completer):
                """Autocompletes alias triggers using registered mappings and system CLI commands."""
                def __init__(self, mappings: List[Dict[str, Any]], shell: str):
                    self.mappings = mappings
                    self.shell = shell
                    self._engine = None

                def get_completions(self, document, complete_event):
                    word = document.get_word_before_cursor()
                    seen = set()
                    prefix_matches = []
                    substr_matches = []

                    for m in self.mappings:
                        alias = str(m.get("alias", "")).strip()
                        if not alias or alias in seen:
                            continue
                        seen.add(alias)

                        templates = m.get("templates", {})
                        target_prev = templates.get(self.shell) or templates.get("universal") or (next(iter(templates.values())) if templates else "")
                        desc = m.get("desc", "")
                        meta = f"-> {target_prev}" if target_prev else desc

                        if not word:
                            prefix_matches.append((alias, meta))
                        elif alias.lower().startswith(word.lower()):
                            prefix_matches.append((alias, meta))
                        elif word.lower() in alias.lower():
                            substr_matches.append((alias, meta))

                    for a, m_desc in prefix_matches + substr_matches:
                        yield Completion(
                            text=a,
                            start_position=-len(word),
                            display=a,
                            display_meta=m_desc[:45] if m_desc else "",
                        )

                    if word and len(word) >= 1:
                        try:
                            if self._engine is None:
                                self._engine = CarapaceEngine()
                            tools = self._engine.get_supported_tools()
                            count = 0
                            for t in sorted(tools):
                                if t not in seen and t.startswith(word.lower()):
                                    yield Completion(
                                        text=t,
                                        start_position=-len(word),
                                        display=t,
                                        display_meta="System CLI tool",
                                    )
                                    count += 1
                                    if count >= 10:
                                        break
                        except Exception:
                            pass

            # Step 1: Input trigger alias
            prompt_1 = HTML("<ansicyan><b>╭─ [1/2] Alias Trigger</b> ❯ </ansicyan>")
            alias_completer = _AliasTriggerCompleter(self.mappings, self.current_shell)
            alias_name = prompt(
                prompt_1,
                completer=alias_completer,
                complete_while_typing=True,
                style=PT_STYLE,
            ).strip()
            if not alias_name:
                con.print("[yellow]Cancelled (empty alias name).[/]\n")
                return 0

            # Step 2: Input target command
            existing_target = ""
            for m in self.mappings:
                if m.get("alias") == alias_name:
                    templates = m.get("templates", {})
                    existing_target = templates.get(self.current_shell) or templates.get("universal") or (next(iter(templates.values())) if templates else "")
                    break

            target_completer = ThreadedCompleter(
                DualStateCompleter(
                    current_shell=self.current_shell,
                    plugin_manager=getattr(self.context, "plugin_manager", None) if self.context else None,
                )
            )

            prompt_2 = HTML("<ansicyan><b>╰─ [2/2] Target Command</b> ❯ </ansicyan>")
            target_cmd = prompt(
                prompt_2,
                default=existing_target,
                completer=target_completer,
                complete_while_typing=True,
                style=PT_STYLE,
            )
            if not target_cmd.strip():
                con.print("[yellow]Cancelled (empty target command).[/]\n")
                return 0

            return self._handle_bracket_add([alias_name, target_cmd], con)

        except (KeyboardInterrupt, EOFError):
            con.print("\n[yellow]Cancelled.[/]\n")
            return 0
        except Exception:
            try:
                con.print("[bold #00f0ff]╭─ [1/2] Alias Trigger:[/] ", end="")
                alias_name = input().strip()
                if not alias_name:
                    return 0
                con.print("[bold #00f0ff]╰─ [2/2] Target Command:[/] ", end="")
                target_cmd = input()
                if not target_cmd.strip():
                    return 0
                return self._handle_bracket_add([alias_name, target_cmd], con)
            except Exception:
                return 0

    # --------------------------------------------------------------------------
    # Subcommand Handlers
    # --------------------------------------------------------------------------

    def _show_list(self, con: Console, platform_filter: Optional[str] = None) -> int:
        """Renders registered alias mappings and Ultra Tools upgrade status."""
        active_shell = platform_filter or self.current_shell

        table = Table(
            title=f"● Kapsel Command Mappings ({active_shell.upper()})",
            title_style="bold #00f0ff",
            border_style="#0891b2",
            header_style="bold white",
        )
        table.add_column("Alias", style="bold #a855f7", width=16)
        table.add_column("Active Template", style="#00f0ff", min_width=32)
        table.add_column("Platforms", style="dim cyan", width=18)
        table.add_column("Engine", justify="center", width=12)
        table.add_column("Description", style="dim white")

        for m in self.mappings:
            alias = m["alias"]
            template = self._resolve_template_for_entry(m, active_shell) or "[dim]N/A[/]"
            desc = m.get("desc", "")
            templates_dict = m.get("templates", {})
            platforms_str = ", ".join(sorted(templates_dict.keys())) or "universal"

            # Check engine: modern or native
            modern_tool = m.get("modern_tool")
            if modern_tool and shutil.which(modern_tool):
                engine_str = f"[bold #10b981]⚡ {modern_tool}[/]"
            elif modern_tool:
                engine_str = f"[dim]{modern_tool} (fallback)[/]"
            else:
                engine_str = "[dim]Native[/]"

            table.add_row(alias, template, platforms_str, engine_str, desc)

        con.print()
        con.print(table)
        con.print(f"[dim]Total: {len(self.mappings)} mappings loaded. Direct execution active inside Kapsel.[/]\n")

        # 2. Render Ultra Tools Status Panel
        ultra_table = Table(
            title="⚡ Ultra Modern CLI Tools Status (Install via 'kps alias ultra')",
            title_style="bold #a855f7",
            border_style="#334155",
            header_style="bold white",
        )
        ultra_table.add_column("Tool", style="bold #00f0ff", width=12)
        ultra_table.add_column("Replaces", style="dim yellow", width=18)
        ultra_table.add_column("Status", justify="center", width=16)
        ultra_table.add_column("Feature Description", style="white")

        installed_count = 0
        for tool in ULTRA_TOOLS:
            is_inst = shutil.which(tool["binary"]) is not None
            if is_inst:
                installed_count += 1
                status = "[bold #10b981]✔ Active[/]"
            else:
                status = "[dim]✖ Not Installed[/]"

            ultra_table.add_row(
                tool["name"],
                tool["replaces"],
                status,
                tool["desc"],
            )

        con.print(ultra_table)
        if installed_count < len(ULTRA_TOOLS):
            con.print(f"[dim]Tip: Run [bold #00f0ff]kps alias ultra[/] to install all missing modern tools at once.[/]\n")
        else:
            con.print(f"[bold #10b981]✔ All {len(ULTRA_TOOLS)} ultra modern tools are installed and ready![/]\n")

        return 0

    def _handle_add(self, sub_args: List[str], con: Console) -> int:
        """
        Adds or updates an alias mapping.
        Usage:
          kps alias add <alias> <template> [-p/--platform <target>] [--desc <description>]
        Defaults to current shell if platform is not explicitly provided.
        """
        if len(sub_args) < 2:
            con.print("[bold #f43f5e]Error:[/] Please specify alias and command template.")
            con.print("[dim]Usage: kps alias add <alias> <template> [-p/--platform <target>] [--desc <text>][/]")
            con.print("[dim]Example: kps alias add 'gcm' 'git commit -m' -p universal[/]\n")
            return 1

        # Extract flags
        raw_platforms = self.current_shell
        desc = ""
        clean_tokens: List[str] = []

        idx = 0
        while idx < len(sub_args):
            token = sub_args[idx]
            if token in ("-p", "--platform", "--platforms") and idx + 1 < len(sub_args):
                raw_platforms = sub_args[idx + 1].lower()
                idx += 2
            elif token.startswith(("--platform=", "--platforms=")):
                raw_platforms = token.split("=", 1)[1].lower()
                idx += 1
            elif token.startswith("-p="):
                raw_platforms = token.split("=", 1)[1].lower()
                idx += 1
            elif token in ("-d", "--desc") and idx + 1 < len(sub_args):
                desc = sub_args[idx + 1]
                idx += 2
            elif token.startswith("--desc="):
                desc = token.split("=", 1)[1]
                idx += 1
            else:
                clean_tokens.append(token)
                idx += 1

        if len(clean_tokens) < 2:
            con.print("[bold #f43f5e]Error:[/] Invalid command syntax. Specify alias and template.")
            return 1

        new_alias = clean_tokens[0]
        new_template = " ".join(clean_tokens[1:])
        if not desc:
            desc = f"Custom alias for {new_alias}"

        # Resolve target platforms
        platform_list = [p.strip() for p in raw_platforms.split(",") if p.strip()]
        expanded_platforms: List[str] = []
        for p in platform_list:
            if p in ("universal", "all"):
                for univ_p in ("universal", "unix", "pwsh", "cmd", "powershell"):
                    if univ_p not in expanded_platforms:
                        expanded_platforms.append(univ_p)
            else:
                if p not in expanded_platforms:
                    expanded_platforms.append(p)

        # Check if alias already exists
        for m in self.mappings:
            if m["alias"] == new_alias:
                for p in expanded_platforms:
                    m.setdefault("templates", {})[p] = new_template
                if desc and desc != f"Custom alias for {new_alias}":
                    m["desc"] = desc
                self._save_mappings()
                plat_str = ", ".join(expanded_platforms)
                con.print(f"[bold #10b981]✔ Updated alias '[#00f0ff]{new_alias}[/]' ([cyan]{plat_str}[/]) -> '[#a855f7]{new_template}[/]'.[/]\n")
                return 0

        # Add new entry
        new_templates = {p: new_template for p in expanded_platforms}
        new_entry: Dict[str, Any] = {
            "alias": new_alias,
            "desc": desc,
            "templates": new_templates,
        }
        self.mappings.append(new_entry)
        self._save_mappings()
        plat_str = ", ".join(expanded_platforms)
        con.print(f"[bold #10b981]✔ Successfully added alias '[#00f0ff]{new_alias}[/]' for platforms [cyan]{plat_str}[/]:[/]")
        con.print(f"    [dim]->[/] [bold #a855f7]{new_template}[/]\n")
        return 0

    def _handle_remove(self, sub_args: List[str], con: Console) -> int:
        """Removes an alias or specific platform template."""
        if not sub_args:
            con.print("[bold #f43f5e]Error:[/] Please specify the alias to remove.")
            con.print("[dim]Usage: kps alias remove <alias> [-p/--platform <target>][/]\n")
            return 1

        raw_platform = None
        clean_tokens: List[str] = []
        idx = 0
        while idx < len(sub_args):
            token = sub_args[idx]
            if token in ("-p", "--platform", "--platforms") and idx + 1 < len(sub_args):
                raw_platform = sub_args[idx + 1].lower()
                idx += 2
            elif token.startswith(("--platform=", "--platforms=")):
                raw_platform = token.split("=", 1)[1].lower()
                idx += 1
            elif token.startswith("-p="):
                raw_platform = token.split("=", 1)[1].lower()
                idx += 1
            else:
                clean_tokens.append(token)
                idx += 1

        if not clean_tokens:
            con.print("[bold #f43f5e]Error:[/] Missing alias name.")
            return 1

        target_alias = clean_tokens[0]

        target_platforms = [p.strip() for p in raw_platform.split(",") if p.strip()] if raw_platform else None

        for m in self.mappings:
            if m["alias"] == target_alias:
                templates = m.get("templates", {})
                if target_platforms:
                    removed_any = False
                    for tp in target_platforms:
                        if tp in templates:
                            del templates[tp]
                            removed_any = True
                    if not templates:
                        self.mappings.remove(m)
                    self._save_mappings()
                    if removed_any:
                        con.print(f"[bold #10b981]✔ Removed platforms '[cyan]{', '.join(target_platforms)}[/]' from alias '[#00f0ff]{target_alias}[/]'.[/]\n")
                        return 0
                    else:
                        con.print(f"[yellow]Platforms '{', '.join(target_platforms)}' not found in alias '{target_alias}'.[/]\n")
                        return 1
                else:
                    self.mappings.remove(m)
                    self._save_mappings()
                    con.print(f"[bold #10b981]✔ Successfully removed alias '[#00f0ff]{target_alias}[/]'.[/]\n")
                    return 0

        con.print(f"[yellow]Alias '{target_alias}' not found in mappings.[/]\n")
        return 1

    def _handle_test(self, sub_args: List[str], con: Console) -> int:
        """Tests and previews translation across platforms."""
        if not sub_args:
            con.print("[bold #f43f5e]Error:[/] Please provide a command line to test.")
            con.print("[dim]Usage: kps alias test <command...>[/]\n")
            return 1

        test_line = " ".join(sub_args)
        is_handled, translated = self.filter_command(test_line)

        con.print(f"\n[bold #00f0ff]● Alias Translation Test[/]")
        con.print(f"  [dim]Input Command:[/]      [white]{test_line}[/]")
        con.print(f"  [dim]Active Shell:[/]       [white]{self.current_shell}[/]")

        if is_handled:
            con.print(f"  [dim]Active Translation:[/] [bold #10b981]{translated}[/]\n")
        else:
            con.print(f"  [dim]Active Translation:[/] [yellow]No alias match (passed through directly)[/]\n")

        # Preview across other shells
        preview_table = Table(box=None, padding=(0, 2))
        preview_table.add_column("Shell", style="cyan", width=12)
        preview_table.add_column("Preview Output", style="white")

        for sh in ("pwsh", "cmd", "unix"):
            # Mock shell
            orig_sh = self.current_shell
            self.current_shell = sh
            h, t = self.filter_command(test_line)
            self.current_shell = orig_sh
            preview_table.add_row(sh, t if h else "[dim]pass-through[/]")

        con.print(preview_table)
        con.print()
        return 0

    def _handle_reset(self, sub_args: List[str], con: Console) -> int:
        """Resets mappings to baseline defaults."""
        self.mappings = [dict(m) for m in DEFAULT_MAPPINGS]
        self._save_mappings()
        con.print("[bold #10b981]✔ Reset all alias mappings to baseline defaults (36+ Linux-First commands).[/]\n")
        return 0

    def _handle_ultra(self, sub_args: List[str], con: Console) -> int:
        """
        One-click installation for the modern, high-performance CLI tools suite
        (eza, bat, ripgrep, fd, procs, dust, bottom, gping, etc.).
        Delegates package installation to Kapsel's unified package manager (kps install).
        """
        con.print("\n[bold #00f0ff]🚀 Kapsel Ultra Modern CLI Tools Suite Installer[/]")
        con.print("[dim]Installs eza, bat, ripgrep, fd, procs, dust, bottom, and more via kps install.[/]\n")

        is_dry_run = "--dry-run" in sub_args or "-n" in sub_args
        missing = [t for t in ULTRA_TOOLS if not shutil.which(t["binary"])]

        if not missing:
            con.print("[bold #10b981]✔ All modern Ultra CLI tools are already installed and active on your system![/]\n")
            return 0

        con.print(f"Found [bold yellow]{len(missing)}[/] tools to install:")
        for t in missing:
            con.print(f"  [bold #a855f7]•[/] [bold white]{t['name']}[/] [dim]({t['replaces']})[/]: {t['desc']}")
        con.print()

        if is_dry_run:
            con.print("[yellow]Dry-run mode active. No packages were installed.[/]\n")
            return 0

        pkgs = [t["name"] for t in missing]
        extra_flags = [a for a in sub_args if a.startswith("-")]
        install_args = extra_flags + pkgs

        con.print(f"[cyan]Installing via Kapsel Installer (kps install):[/] {' '.join(pkgs)}...\n")

        # 1. First attempt: Invoke install command via Kapsel command registry in-process
        try:
            from kapsel.completion.kps.registry import get_kps_registry
            registry = get_kps_registry()
            install_cmd = registry.get_feature_command("install")
            if install_cmd:
                return install_cmd.handler(install_args, con) or 0
        except Exception:
            pass

        # 2. Second attempt: Invoke via dispatch_kps
        try:
            from kapsel.completion.kps.dispatcher import dispatch_kps
            res = dispatch_kps("kps install " + " ".join(install_args), con)
            if res is not None:
                return res
        except Exception:
            pass

        # 3. Third attempt: Fallback to invoking kps CLI or python module
        try:
            kps_bin = shutil.which("kps")
            if kps_bin:
                res = subprocess.run([kps_bin, "install"] + install_args)
                return res.returncode
            else:
                res = subprocess.run([sys.executable, "-m", "kapsel.cli", "kps", "install"] + install_args)
                return res.returncode
        except Exception as e:
            con.print(f"[bold #f43f5e]Failed to execute kps install:[/] {e}\n")
            return 1

    def _show_help(self, con: Console) -> int:
        con.print("\n[bold #00f0ff]● Kapsel Alias Plugin (Command Mapping & Modern Tools)[/]")
        con.print("[dim]Transparently maps Linux-first commands in Kapsel REPL with progressive modern tool enhancement.[/]\n")
        con.print("[bold white]Usage:[/]")
        con.print("  [bold #a855f7]kps alias[/] (or list)              Display active mappings and ultra modern tools status")
        con.print("  [bold #a855f7]kps alias add <alias> <cmd>[/]      Add alias for current platform (or -p universal)")
        con.print("  [bold #a855f7]kps alias remove <alias>[/]         Remove an alias or platform template (-p)")
        con.print("  [bold #a855f7]kps alias test <command...>[/]      Preview translation without executing")
        con.print("  [bold #a855f7]kps alias reset[/]                  Reset mappings to default baseline")
        con.print("  [bold #a855f7]kps alias ultra[/]                  One-click install modern CLI tools (eza, bat, rg, etc.)\n")
        return 0
