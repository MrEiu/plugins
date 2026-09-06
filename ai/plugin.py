"""
AI (Terminal LLM Assistant) Plugin for Kapsel.
Native terminal AI engine powered by the official OpenAI Python SDK.
Provides intelligent command generation, error auto-fix, git commit generation,
command dissection, workspace reconnaissance, and pipeline stream analysis.
All comments and descriptions are in English.
"""

import os
from pathlib import Path
import sys
from typing import List, Optional

from rich.console import Console
from rich.panel import Panel

from kapsel.core.plugin.base import KapselPlugin, PluginManifest
from kapsel.core.plugin.context import PluginContext
from kapsel.ui.banner import ensure_utf8_io
from .config import get_ai_config_file, load_ai_config, save_ai_config, get_provider_models
from .client import AiClient
from .wizard import run_ai_setup_wizard
from .actions import (
    action_do,
    action_fix,
    action_commit,
    action_explain,
    action_pipe,
    action_scout,
)

ensure_utf8_io()


def _get_client(con: Console) -> Optional[AiClient]:
    """Loads configuration and instantiates an AiClient, or warns user to run init."""
    cfg = load_ai_config()
    if not cfg:
        con.print("\n[bold #f59e0b]Notice:[/] AI configuration has not been initialized yet.")
        con.print("Please run the guided setup wizard: [bold #00f0ff]kps ai init[/]\n")
        return None

    try:
        return AiClient(
            api_base=cfg.get("api_base", "https://api.openai.com/v1"),
            api_key=cfg.get("api_key", ""),
            model=cfg.get("model", "gpt-5.6-sol"),
            timeout=float(cfg.get("timeout", 35.0)),
        )
    except Exception as e:
        con.print(f"[bold #f43f5e]Failed to initialize AI client:[/] {e}\n")
        return None


class AiPlugin(KapselPlugin):
    """
    Kapsel 'ai' feature plugin powered by OpenAI Python SDK.
    Provides pure terminal interactive AI actions.
    """

    manifest = PluginManifest(
        id="ai",
        name="Ai",
        version="0.1.2",
        description="Native terminal AI assistant powered by OpenAI Python SDK.",
        author="Kapsel Team",
        homepage="https://github.com/MrEiu/plugins/tree/master/ai",
        min_kapsel_version="0.1.0",
        dependencies=[],
        tags=["ai", "llm", "assistant", "terminal", "copilot"],
    )

    def __init__(self) -> None:
        super().__init__()
        self.context: Optional[PluginContext] = None

    def on_load(self, context: PluginContext) -> None:
        """Registers the 'ai' command under 'kps' scope."""
        self.context = context
        context.register_kps_command(
            name="ai",
            handler=self.handle_ai,
            help_text="Terminal AI copilot: nl commands, auto-fix, git commit, explain, scout",
            usage="kps ai [do|fix|commit|explain|scout|config|init] [args...]",
            subcommands={
                "init": "Run interactive guided setup wizard for AI provider and API key",
                "config": "Inspect, test, or switch active AI model and configuration",
                "do": "Generate shell command from natural language with 1-click execution",
                "fix": "Auto-diagnose and propose 1-click fix for the last failed command",
                "?": "Alias for 'fix' (quick error diagnosis)",
                "commit": "Generate Conventional Commit message from git diff and commit",
                "explain": "Dissect and explain shell command flags and arguments",
                "scout": "Reconnaissance workspace project architecture, stack, and entrypoints",
            },
            scope="feature",
        )

    def handle_ai(self, args: List[str], console: Optional[Console] = None) -> int:
        """
        Dispatches 'kps ai' command:
        - Stdin pipe: '<cmd> | kps ai [prompt]' -> action_pipe
        - 'kps ai' (bare)                       -> Help & interactive capabilities card
        - 'kps ai init' / 'kps ai setup'        -> Guided setup wizard
        - 'kps ai config [status|test|model...]' -> Configuration management
        - 'kps ai fix' / 'kps ai ?'             -> Auto error diagnosis from BlockRegistry
        - 'kps ai commit'                       -> Git diff to conventional commit
        - 'kps ai explain [cmd]'                -> Command parameter dissection
        - 'kps ai scout'                        -> Codebase reconnaissance
        - 'kps ai do <nl...>'                   -> Natural language command generator
        - 'kps ai <nl...>'                      -> Default natural language command generator
        """
        con = console or Console(legacy_windows=False)
        executor = getattr(self.context, "executor", None) if self.context else None

        # 1. Pipeline / Stdin stream processor
        try:
            if not sys.stdin.isatty():
                pipe_content = sys.stdin.read().strip()
                if pipe_content:
                    client = _get_client(con)
                    if not client:
                        return 1
                    prompt_text = " ".join(args).strip()
                    return action_pipe(prompt=prompt_text, pipe_content=pipe_content, con=con, client=client)
        except Exception:
            pass

        # 2. Bare invocation or explicit help flag
        if not args or args in (["-h"], ["--help"], ["help"]):
            con.print("\n[bold #00f0ff]🤖 Kapsel AI Copilot (Powered by OpenAI SDK)[/]")
            con.print("[dim]Pure terminal interactive intelligent assistance[/]\n")
            con.print("[bold white]Core Commands:[/]")
            con.print("  [bold #a855f7]kps ai <nl...>[/]               Generate shell command from natural language ([Enter] run, [Tab] copy)")
            con.print("  [bold #a855f7]kps ai fix[/] | [bold #a855f7]kps ai ?[/]         Auto-diagnose last failed command & propose 1-click fix")
            con.print("  [bold #a855f7]kps ai commit[/]               Analyze git diff & generate Conventional Commit")
            con.print("  [bold #a855f7]kps ai explain [cmd][/]        Dissect command syntax, flags, and arguments step-by-step")
            con.print("  [bold #a855f7]kps ai scout[/]                Reconnaissance workspace architecture, tech stack & entrypoints")
            con.print("  [bold #a855f7]<cmd> | kps ai [prompt][/]     Process piped terminal output through AI in real-time\n")
            con.print("[bold white]Configuration:[/]")
            con.print("  [bold #a855f7]kps ai init[/]                 Interactive setup wizard (DeepSeek, SiliconFlow, Ollama, Gemini, OpenAI)")
            con.print("  [bold #a855f7]kps ai config status[/]        Inspect active model and API endpoint")
            con.print("  [bold #a855f7]kps ai config test[/]          Test connectivity with configured model endpoint")
            con.print("  [bold #a855f7]kps ai config model <name>[/]  Switch active model without re-running wizard\n")
            return 0

        sub = args[0].lower()

        # 3. Interactive setup wizard
        if sub in ("init", "setup"):
            return run_ai_setup_wizard(con)

        # 4. Configuration management
        if sub == "config":
            cfg = load_ai_config()
            cfg_file = get_ai_config_file()
            sub_args = args[1:] if len(args) > 1 else ["status"]
            action = sub_args[0].lower()

            if action == "status":
                if not cfg:
                    con.print("[yellow]AI configuration has not been initialized yet. Run:[/] [bold #00f0ff]kps ai init[/]")
                    return 1

                key = cfg.get("api_key", "")
                masked_key = f"{key[:4]}...{key[-4:]}" if len(key) > 8 else ("(none)" if not key else "***")

                con.print(f"\n[bold #00f0ff]● Active AI Configuration[/]")
                con.print(f"  [dim]Config File:[/] {cfg_file}")
                con.print(f"  [dim]Provider:[/] [white]{cfg.get('provider_name', cfg.get('provider', 'Custom'))}[/]")
                con.print(f"  [dim]Active Model:[/] [bold #10b981]{cfg.get('model', 'Unknown')}[/]")
                con.print(f"  [dim]API Base URL:[/] {cfg.get('api_base', 'Default')}")
                con.print(f"  [dim]API Key:[/] [dim]{masked_key}[/]\n")
                return 0

            elif action == "test":
                if not cfg:
                    con.print("[yellow]AI configuration has not been initialized yet. Run:[/] [bold #00f0ff]kps ai init[/]")
                    return 1
                con.print(f"[dim]Sending test query to {cfg.get('model')}...[/]")
                client = _get_client(con)
                if not client:
                    return 1
                try:
                    res = client.chat_completion([{"role": "user", "content": "Respond with 'pong' only"}])
                    con.print(f"[bold #10b981]✔ Connectivity verified successfully![/] Response: [dim]{res.strip()}[/]\n")
                    return 0
                except Exception as e:
                    con.print(f"[bold #f43f5e]Connection test failed:[/] {e}\n")
                    return 1

            elif action in ("model", "models"):
                if len(sub_args) < 2 or action == "models":
                    con.print("[yellow]Usage:[/] kps ai config model <model_name>")
                    if cfg:
                        con.print(f"[dim]Current model:[/] [bold #10b981]{cfg.get('model')}[/]")
                        available = get_provider_models(
                            provider_id=cfg.get("provider", "custom"),
                            api_base=cfg.get("api_base"),
                            api_key=cfg.get("api_key"),
                        )
                        if available:
                            con.print(f"[dim]Available models:[/] {', '.join(available[:10])}")
                    return 0 if action == "models" else 1
                if not cfg:
                    con.print("[yellow]AI configuration has not been initialized yet. Run:[/] [bold #00f0ff]kps ai init[/]")
                    return 1
                new_model = sub_args[1].strip()
                cfg["model"] = new_model
                save_ai_config(cfg)
                con.print(f"[bold #10b981]✔ Switched active AI model to:[/] [bold #00f0ff]{new_model}[/]\n")
                return 0

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
                con.print("[bold #f43f5e]Unknown config action.[/] Options: status, test, model <name>, edit")
                return 1

        # Check client for remaining operational commands
        client = _get_client(con)
        if not client:
            return 1

        # 5. One-click error auto-fix
        if sub in ("fix", "?"):
            return action_fix(con=con, client=client, executor=executor)

        # 6. Git diff to conventional commit
        if sub == "commit":
            return action_commit(con=con, client=client)

        # 7. Command parameter dissection
        if sub == "explain":
            cmd_text = " ".join(args[1:])
            return action_explain(command_text=cmd_text, con=con, client=client)

        # 8. Workspace reconnaissance
        if sub == "scout":
            return action_scout(con=con, client=client)

        # 9. Natural language command generator ('do' prefix or default prompt)
        if sub == "do":
            prompt_tokens = args[1:]
        else:
            prompt_tokens = args

        if not prompt_tokens:
            con.print("[bold #f43f5e]Error:[/] Please provide a prompt describing the command you want to generate.")
            con.print("[dim]Example: kps ai list all docker containers[/]\n")
            return 1

        return action_do(
            prompt_text=" ".join(prompt_tokens),
            con=con,
            client=client,
            executor=executor,
        )
