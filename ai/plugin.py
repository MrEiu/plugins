"""
AI (Terminal LLM Assistant) Plugin for Kapsel.
Bridges 'aichat' to provide command-line natural language assistance, command generation, and code queries.
Includes an interactive guided setup wizard ('kps ai init') for effortless LLM configuration.
All comments and descriptions are in English.
"""

import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import List, Optional

from rich.console import Console
from rich.panel import Panel
import yaml

from kapsel.core.plugin.base import KapselPlugin, PluginManifest
from kapsel.core.plugin.context import PluginContext
from kapsel.storage.config import get_kapsel_dir
from kapsel.ui.banner import ensure_utf8_io
from .wizard import get_ai_config_dir, get_ai_config_file, run_ai_setup_wizard, verify_ai_configuration

ensure_utf8_io()


def _resolve_aichat_executable() -> Optional[str]:
    """
    Resolves the aichat executable from common locations:
    1. System PATH
    2. Scoop shims / apps directory (~/scoop/shims/aichat.exe)
    3. Kapsel local bin directory (~/.kapsel/bin/aichat.exe or aichat)
    4. Cargo bin directory (~/.cargo/bin)
    5. Windows WinGet links directory
    """
    # 1. System PATH
    p = shutil.which("aichat")
    if p:
        return p

    # 2. Scoop paths
    scoop_shim = Path.home() / "scoop/shims/aichat.exe"
    if scoop_shim.exists():
        return str(scoop_shim)
    scoop_app = Path.home() / "scoop/apps/aichat/current/aichat.exe"
    if scoop_app.exists():
        return str(scoop_app)

    # 3. Kapsel local bin directory
    is_win = sys.platform == "win32"
    local_bin = get_kapsel_dir() / "bin" / ("aichat.exe" if is_win else "aichat")
    if local_bin.exists():
        return str(local_bin)

    # 4. Cargo bin
    cargo_bin = Path.home() / ".cargo/bin" / ("aichat.exe" if is_win else "aichat")
    if cargo_bin.exists():
        return str(cargo_bin)

    # 5. WinGet links
    winget_link = Path.home() / "AppData/Local/Microsoft/WinGet/Links/aichat.exe"
    if winget_link.exists():
        return str(winget_link)

    return None


def _run_aichat(args: List[str], console: Optional[Console] = None) -> int:
    """Executes aichat with Kapsel-managed environment settings."""
    con = console or Console(legacy_windows=False)
    aichat_bin = _resolve_aichat_executable()

    if not aichat_bin:
        con.print("[bold #f43f5e]Error:[/] [white]aichat CLI tool is not found.[/]")
        con.print("[dim]To install aichat automatically, run:[/] [bold #00f0ff]kapsel add ai[/]\n")
        return 1

    cfg_file = get_ai_config_file()
    if not cfg_file.exists():
        con.print("[bold #f59e0b]Notice:[/] [white]AI configuration has not been initialized yet.[/]")
        con.print("[dim]Please run the setup wizard first:[/] [bold #00f0ff]kps ai init[/]\n")
        return 1

    env = os.environ.copy()
    env["AICHAT_CONFIG_DIR"] = str(get_ai_config_dir())
    env["PYTHONIOENCODING"] = "utf-8"

    try:
        # Stream process directly in terminal so markdown colors and interactive confirmations work
        proc = subprocess.run([aichat_bin] + args, env=env)
        return proc.returncode
    except KeyboardInterrupt:
        con.print("\n[dim]Aborted.[/]")
        return 130
    except Exception as e:
        con.print(f"[bold #f43f5e]Failed to execute aichat:[/] {e}")
        return 1


class AiPlugin(KapselPlugin):
    """
    Kapsel 'ai' feature plugin integrating aichat.
    Provides fast command-line AI queries, command execution, and interactive wizard setup.
    """

    manifest = PluginManifest(
        id="ai",
        name="Ai",
        version="0.1.0",
        description="Terminal AI assistant powered by aichat with guided setup wizard.",
        author="Kapsel Team",
        homepage="https://github.com/MrEiu/plugins/tree/master/ai",
        min_kapsel_version="0.1.0",
        dependencies=["aichat"],
        tags=["ai", "llm", "aichat", "assistant", "productivity", "tools"],
    )

    def on_load(self, context: PluginContext) -> None:
        """Registers the 'ai' functional command under 'kps' scope."""
        context.register_kps_command(
            name="ai",
            handler=self.handle_ai,
            help_text="Terminal AI assistant: ask questions ('ai <prompt>'), generate commands ('ai -e <cmd>'), or init ('ai init')",
            usage="kps ai [init|config|-e|-c] [prompt...]",
            subcommands={
                "init": "Run interactive guided setup wizard for AI provider and API key",
                "config": "Inspect, test, or edit current AI configuration",
                "-e": "Generate shell command from natural language and execute upon confirmation",
                "--execute": "Generate shell command from natural language and execute upon confirmation",
                "-c": "Output pure code snippet without chatter",
                "--code": "Output pure code snippet without chatter",
            },
            scope="feature",
        )

    def handle_ai(self, args: List[str], console: Optional[Console] = None) -> int:
        """
        Dispatches 'kps ai' command:
        - 'kps ai' (bare)          -> Shows help & quick usage guide (no REPL session)
        - 'kps ai init'            -> Launches interactive guided setup wizard
        - 'kps ai config [sub]'    -> Status, test, or edit configuration
        - 'kps ai -e <prompt...>'  -> Natural language command generation & execution
        - 'kps ai -c <prompt...>'  -> Pure code snippet output
        - 'kps ai <prompt...>'     -> Single-turn question & response
        """
        con = console or Console(legacy_windows=False)

        # 1. Bare invocation or explicit help flag -> Display usage guide (DO NOT enter REPL)
        if not args or args in (["-h"], ["--help"], ["help"]):
            con.print("\n[bold #00f0ff]🤖 Kapsel AI Assistant (Powered by aichat)[/]")
            con.print("[dim]Command-line intelligent assistance with guided configuration[/]\n")
            con.print("[bold white]Usage:[/]")
            con.print("  [bold #a855f7]kps ai init[/]                  Run interactive guided setup wizard (OpenAI, Gemini, Claude, DeepSeek...)")
            con.print("  [bold #a855f7]kps ai <prompt...>[/]           Ask a question directly (e.g. 'kps ai how to extract tar.gz')")
            con.print("  [bold #a855f7]kps ai -e <prompt...>[/]        Generate shell command from natural language and run it")
            con.print("  [bold #a855f7]kps ai -c <prompt...>[/]        Output pure code snippet (suitable for file redirection)")
            con.print("  [bold #a855f7]kps ai config status[/]         View active model provider and configuration")
            con.print("  [bold #a855f7]kps ai config test[/]           Test API connectivity with configured model\n")
            return 0

        sub = args[0].lower()

        # 2. Interactive setup wizard ('kps ai init' or 'kps ai setup')
        if sub in ("init", "setup"):
            return run_ai_setup_wizard(con)

        # 3. Configuration management ('kps ai config [status|test|edit]')
        if sub == "config":
            cfg_file = get_ai_config_file()
            sub_args = args[1:] if len(args) > 1 else ["status"]
            action = sub_args[0].lower()

            if action == "status":
                if not cfg_file.exists():
                    con.print("[yellow]AI configuration has not been initialized yet. Run:[/] [bold #00f0ff]kps ai init[/]")
                    return 1
                try:
                    data = yaml.safe_load(cfg_file.read_text(encoding="utf-8"))
                    model = data.get("model", "Unknown")
                    clients = data.get("clients", [])
                    client_name = clients[0].get("name", "Unknown") if clients else "None"
                    client_type = clients[0].get("type", "Unknown") if clients else "None"
                    api_base = clients[0].get("api_base", "Default") if clients else "Default"

                    con.print(f"\n[bold #00f0ff]● Active AI Configuration[/]")
                    con.print(f"  [dim]Config File:[/] {cfg_file}")
                    con.print(f"  [dim]Active Model:[/] [bold #10b981]{model}[/]")
                    con.print(f"  [dim]Provider Client:[/] {client_name} ({client_type})")
                    con.print(f"  [dim]API Base URL:[/] {api_base}\n")
                    return 0
                except Exception as e:
                    con.print(f"[bold #f43f5e]Failed to parse config file:[/] {e}")
                    return 1

            elif action == "test":
                if not cfg_file.exists():
                    con.print("[yellow]AI configuration has not been initialized yet. Run:[/] [bold #00f0ff]kps ai init[/]")
                    return 1
                con.print("[dim]Sending test query to configured AI model...[/]")
                res = _run_aichat(["ping, please reply with 'pong' only"], con)
                return res

            elif action in ("edit", "path"):
                con.print(f"Config path: [bold #00f0ff]{cfg_file}[/]")
                if action == "edit":
                    if sys.platform == "win32":
                        os.system(f'notepad "{cfg_file}"')
                    else:
                        editor = os.environ.get("EDITOR", "nano")
                        os.system(f'{editor} "{cfg_file}"')
                return 0

            else:
                con.print("[bold #f43f5e]Unknown config action.[/] Options: status, test, edit")
                return 1

        # 4. Command generation & execution mode ('-e' / '--execute')
        if sub in ("-e", "--execute"):
            prompt_tokens = args[1:]
            if not prompt_tokens:
                con.print("[bold #f43f5e]Error:[/] Please provide a prompt describing the command you want to generate.")
                con.print("[dim]Example: kps ai -e list all python files modified today[/]\n")
                return 1
            return _run_aichat(["-e", " ".join(prompt_tokens)], con)

        # 5. Code-only mode ('-c' / '--code')
        if sub in ("-c", "--code"):
            prompt_tokens = args[1:]
            if not prompt_tokens:
                con.print("[bold #f43f5e]Error:[/] Please provide a prompt describing the code you want to generate.")
                con.print("[dim]Example: kps ai -c quicksort function in python[/]\n")
                return 1
            return _run_aichat(["-c", " ".join(prompt_tokens)], con)

        # 6. Single-turn prompt inquiry
        # Forward prompt arguments to aichat as a single question string
        query_text = " ".join(args)
        return _run_aichat([query_text], con)
