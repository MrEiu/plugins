"""
Translate Plugin for Kapsel.
Translates command outputs, pipes, and text using translate-shell (trans).
Supports both post-command diagnosis ('tr') and inline pipe filtering ('<cmd> | tr').
All comments and docstrings are in English.
"""

from pathlib import Path
import re
import shlex
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple

from rich.console import Console

from kapsel.core.plugin.base import KapselPlugin, PluginManifest
from kapsel.core.plugin.context import PluginContext
from kapsel.core.plugin.hooks import HookType

try:
    from .engine import (
        detect_target_language,
        execute_trans,
        extract_key_output_for_translation,
        get_last_command_block,
        render_text_translation,
        render_translation_card,
        resolve_trans_executable,
        resolve_translator_executable,
    )
    from .install import print_installation_guide
except ImportError:
    from plugins.trans.engine import (
        detect_target_language,
        execute_trans,
        extract_key_output_for_translation,
        get_last_command_block,
        render_text_translation,
        render_translation_card,
        resolve_trans_executable,
        resolve_translator_executable,
    )
    from plugins.trans.install import print_installation_guide



COMMON_LANGUAGES = [
    {"code": "zh", "name": "Simplified Chinese (简体中文)"},
    {"code": "en", "name": "English (英语)"},
    {"code": "ja", "name": "Japanese (日本語)"},
    {"code": "ko", "name": "Korean (한국어)"},
    {"code": "zh-TW", "name": "Traditional Chinese (繁體中文)"},
    {"code": "fr", "name": "French (Français)"},
    {"code": "de", "name": "German (Deutsch)"},
    {"code": "es", "name": "Spanish (Español)"},
    {"code": "ru", "name": "Russian (Русский)"},
]


class TranslatePlugin(KapselPlugin):
    """
    Kapsel Translate Plugin:
    Smart terminal output and multilingual translation dispatcher.
    """

    manifest = PluginManifest(
        id="trans",
        name="Translate",
        version="0.1.1",
        description="Terminal command output and multilingual translation powered by fanyi (Windows) and translate-shell (Linux/macOS).",
        author="Kapsel Team",
        homepage="https://github.com/MrEiu/plugins/tree/master/trans",
        min_kapsel_version="0.1.0",
        tags=["translate", "trans", "tr", "fanyi", "i18n", "dictionary", "translate-shell"],
    )

    def __init__(self) -> None:
        super().__init__()
        self.context: Optional[PluginContext] = None

    def on_load(self, context: PluginContext) -> None:
        self.context = context

        # 1. Pre-execution filter: intercepts 'tr', 'kps tr', '<cmd> | tr'
        context.register_hook(HookType.FILTER_COMMAND, self.filter_command)

        # 2. Dynamic autocompletion for language tags (:zh, :en, :ja, etc.)
        context.register_hook(HookType.PROVIDE_COMPLETIONS, self.provide_completions)

        # 3. Register functional commands under kps namespace
        context.register_kps_command(
            name="trans",
            handler=self.handle_translate,
            help_text="Translate command output or text using fanyi or translate-shell",
            usage="kps trans [options] [text]",
            scope="feature",
        )
        context.register_kps_command(
            name="tr",
            handler=self.handle_translate,
            help_text="Alias for 'kps trans'",
            usage="kps tr [options] [text]",
            scope="feature",
        )

    def handle_translate(self, args: List[str], console: Optional[Console] = None) -> int:
        """Main handler for 'kps trans' / 'tr'."""
        con = console or Console()

        # Check if any translation tool is available (fanyi on Windows, trans on Unix)
        engine_type, tool = resolve_translator_executable()
        if not tool:
            print_installation_guide(con)
            return 1

        # Case 1: No arguments -> Translate output of last executed command
        if not args:
            return self._translate_last_command(con)

        # Case 2: Help flag
        if args[0] in ("-h", "--help", "help"):
            self._render_help(con)
            return 0

        # Case 3: Text query or language-specified translation
        target_lang: Optional[str] = None
        source_lang: Optional[str] = None
        text_tokens: List[str] = []

        idx = 0
        while idx < len(args):
            arg = args[idx]
            # Match language prefix like ':zh', ':ja', or 'en:zh'
            if (arg.startswith(":") and len(arg) > 1) or (":" in arg and not arg.startswith("http")):
                parts = arg.split(":")
                if len(parts) == 2:
                    source_lang = parts[0] if parts[0] else None
                    target_lang = parts[1] if parts[1] else None
                idx += 1
                continue
            text_tokens.append(arg)
            idx += 1

        if not text_tokens:
            # If only language was provided (e.g. 'tr :ja'), translate last command to that language!
            return self._translate_last_command(con, target_lang=target_lang, source_lang=source_lang)

        source_text = " ".join(text_tokens)
        code, translated = execute_trans(
            source_text,
            target_lang=target_lang,
            source_lang=source_lang,
            brief=True,
        )
        if code == 0:
            resolved_target = detect_target_language(source_text, target_lang)
            render_text_translation(source_text, translated, resolved_target, con)
            return 0

        con.print(f"[bold #f43f5e]Translation error:[/] {translated}")
        return code

    def _translate_last_command(
        self,
        con: Console,
        target_lang: Optional[str] = None,
        source_lang: Optional[str] = None,
    ) -> int:
        """Extracts and translates the output of the most recent command."""
        block = get_last_command_block()
        if not block:
            con.print("\n[dim]ℹ No previous command output found to translate.[/]\n")
            return 0

        snippet, is_error = extract_key_output_for_translation(block)
        if not snippet.strip():
            con.print(f"\n[dim]ℹ Previous command '{block.command}' produced no captured output.[/]\n")
            return 0

        resolved_target = detect_target_language(snippet, target_lang)

        con.print(f"[dim]Translating output of '[bold white]{block.command}[/]' to {resolved_target}...[/]")
        code, translated = execute_trans(
            snippet,
            target_lang=resolved_target,
            source_lang=source_lang,
            brief=True,
        )
        if code == 0:
            render_translation_card(
                command=block.command,
                exit_code=block.exit_code,
                original=snippet,
                translated=translated,
                console=con,
                target_lang=resolved_target,
            )
            return 0

        con.print(f"[bold #f43f5e]Translation error:[/] {translated}")
        return code

    def filter_command(self, raw_command: str) -> Tuple[bool, str]:
        """
        Intercepts:
        1. 'tr [args]' / 'kps tr [args]' / 'kps trans [args]' -> direct translation
        2. '<cmd> | tr' / '<cmd> | tr :<lang>' -> pipeline rewrite to trans
        """
        stripped = raw_command.strip()
        if not stripped:
            return False, raw_command

        tokens = stripped.split()
        prefix = tokens[0].lower()

        # 1. Pipeline rewrite: '<cmd> | tr' or '<cmd> | tr :<lang>'
        # Check if the command line ends with pipe to tr
        pipe_match = re.search(r"\|\s*(?:kps\s+)?(?:tr|trans)(?:\s+(:[\w\-]+))?\s*$", stripped)
        if pipe_match:
            engine_type, tool = resolve_translator_executable()
            if not tool:
                con = Console()
                print_installation_guide(con)
                return True, ""

            upstream = stripped[:pipe_match.start()].rstrip()
            if engine_type == "fanyi":
                # fanyi pipes input directly: '<upstream> | "path/to/fanyi"'
                rewritten = f'{upstream} | "{tool}"'
            else:
                lang_arg = pipe_match.group(1) or ":zh-CN"
                # Rewrite pipe to trans executable: '<upstream> | "path/to/trans" -b <lang>'
                rewritten = f'{upstream} | "{tool}" -b {lang_arg}'
            return True, rewritten

        # 2. Direct command: 'tr' or 'kps tr' or 'kps trans'
        if prefix == "tr":
            con = Console()
            self.handle_translate(tokens[1:], con)
            return True, ""

        if stripped.lower().startswith("kps tr") or stripped.lower().startswith("kps trans"):
            sub_tokens = tokens[2:]
            con = Console()
            self.handle_translate(sub_tokens, con)
            return True, ""

        return False, raw_command

    def provide_completions(self, text_before_cursor: str) -> List[dict]:
        """Provides language code autocompletion when typing 'tr :' or 'kps tr :'."""
        stripped = text_before_cursor.lstrip()
        matched = False
        for p in ("kps trans ", "kps tr ", "tr "):
            if stripped.startswith(p):
                matched = True
                remainder = stripped[len(p):]
                break

        if not matched:
            return []

        # If user is typing language tag (starts with ':')
        if remainder.startswith(":"):
            prefix = remainder[1:].lower()
            completions = []
            for lang in COMMON_LANGUAGES:
                if lang["code"].lower().startswith(prefix):
                    completions.append({
                        "text": f":{lang['code']}",
                        "display": f":{lang['code']}",
                        "display_meta": lang["name"],
                        "start_position": -len(remainder),
                    })
            return completions

        return []

    def _render_help(self, con: Console) -> None:
        """Renders help information for translation commands."""
        con.print("\n[bold #00f0ff]Kapsel Translate (tr) - Command Output & Multilingual Translator[/]")
        con.print("[dim]Powered by translate-shell (trans). Automatically translates command outputs and text.[/]\n")
        con.print("[bold white]Usage:[/]")
        con.print("  [#38bdf8]tr[/]                       Translate output / errors of the previous command")
        con.print("  [#38bdf8]tr[/] <text>                Translate text (auto-detects English <-> Chinese)")
        con.print("  [#38bdf8]tr[/] :<lang> [text]        Translate text (or last command) to target language")
        con.print("  [#38bdf8]<cmd> | tr[/]               Pipe any command's output through translate-shell\n")
        con.print("[bold white]Common Language Codes:[/]")
        for lang in COMMON_LANGUAGES:
            con.print(f"  • [bold green]:{lang['code']:<6}[/] [white]{lang['name']}[/]")
        con.print()


Plugin = TranslatePlugin
