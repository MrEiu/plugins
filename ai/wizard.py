"""
Kapsel AI Plugin - Interactive Setup Wizard.
Guides users step-by-step through configuring LLM providers and models using OpenAI Python SDK.
All comments and descriptions are in English.
"""

from getpass import getpass
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.panel import Panel

from kapsel.ui.banner import ensure_utf8_io
from .config import DEFAULT_PROVIDERS, get_ai_config_file, save_ai_config, load_ai_config, get_provider_models
from .client import AiClient

ensure_utf8_io()


def run_ai_setup_wizard(console: Optional[Console] = None) -> int:
    """
    Runs an interactive terminal wizard to configure an AI provider.
    Saves to ~/.kapsel/ai/config.yaml and verifies connectivity.
    """
    con = console or Console(legacy_windows=False)

    menu_lines = ["[bold #00f0ff]Select an AI model provider to configure:[/]\n"]
    for idx, prov in enumerate(DEFAULT_PROVIDERS, start=1):
        menu_lines.append(f"  [bold #a855f7][{idx}][/] [white]{prov['name']}[/]")

    con.print(Panel("\n".join(menu_lines), title="[bold #00f0ff]🤖 Kapsel AI Setup Wizard (kps ai init)[/]", border_style="#0891b2"))

    # Interactive prompt sequence
    try:
        # 1. Choice of provider
        raw_choice = input(f"Enter choice [1-{len(DEFAULT_PROVIDERS)}] (default: 1): ").strip()
        choice_idx = int(raw_choice) - 1 if raw_choice else 0
        if not (0 <= choice_idx < len(DEFAULT_PROVIDERS)):
            con.print(f"[bold #f43f5e]Invalid selection. Defaulting to {DEFAULT_PROVIDERS[0]['name']}.[/]")
            choice_idx = 0

        selected = DEFAULT_PROVIDERS[choice_idx]
        con.print(f"\n[bold #10b981]✔ Selected:[/] [white]{selected['name']}[/]\n")

        # 2. Base URL
        api_base = selected["api_base"]
        if selected["id"] == "custom":
            raw_base = input("Enter API Base URL (e.g. https://api.my-llm.com/v1): ").strip()
            api_base = raw_base or "http://localhost:8000/v1"
        else:
            prompt_base = input(f"API Base URL [{api_base}]: ").strip()
            if prompt_base:
                api_base = prompt_base

        # 3. API Key
        api_key = ""
        if selected["requires_key"]:
            api_key = getpass(selected["key_prompt"]).strip()
            if not api_key:
                con.print("[yellow]Warning: Empty API key provided. Requests may fail if authentication is required.[/]")
        else:
            con.print("[dim]No API key required for local provider.[/]")

        # 4. Model Selection (Dynamic /models probe with static fallback)
        default_model = selected["model"]
        available_models = get_provider_models(
            provider_id=selected["id"],
            api_base=api_base,
            api_key=api_key,
        )
        if available_models:
            display_models = available_models[:8]
            suffix = f" ... (+{len(available_models) - 8} more)" if len(available_models) > 8 else ""
            con.print(f"[dim]Available models:[/] {', '.join(display_models)}{suffix}")
            if default_model not in available_models and available_models:
                default_model = available_models[0]

        model_input = input(f"Default Model [{default_model}]: ").strip()
        model_name = model_input if model_input else default_model

    except (ValueError, KeyboardInterrupt, EOFError):
        con.print("\n[dim]Setup aborted.[/]")
        return 1

    # 5. Build configuration structure
    cfg_data: Dict[str, Any] = {
        "provider": selected["id"],
        "provider_name": selected["name"],
        "api_base": api_base,
        "api_key": api_key,
        "model": model_name,
        "temperature": 0.1,
    }

    # 6. Save configuration to Kapsel data directory
    save_ai_config(cfg_data)
    target_file = get_ai_config_file()

    con.print(f"\n[bold #10b981]✔ Configuration successfully saved![/]")
    con.print(f"[dim]Config file: {target_file}[/]")

    # 7. Verification test using AiClient
    con.print("\n[dim]Testing connectivity with configured model endpoint...[/]")
    try:
        client = AiClient(api_base=api_base, api_key=api_key, model=model_name, timeout=12.0)
        res = client.chat_completion(
            messages=[{"role": "user", "content": "Respond with 'pong' only"}],
            temperature=0.1,
        )
        if res:
            con.print(f"[bold #10b981]✔ Model responded successfully:[/] [dim]{res[:60]}[/]")
            con.print("\n[bold #10b981]✨ AI setup complete![/] You can now use:")
            con.print("  [bold #00f0ff]kps ai <prompt>[/]     - Natural language to command")
            con.print("  [bold #00f0ff]kps ai fix[/]          - Auto-diagnose and fix last failed command")
            con.print("  [bold #00f0ff]kps ai commit[/]       - Generate Git commit from diff\n")
            return 0
        else:
            con.print("[yellow]Notice: Model connected but returned empty response. Please verify settings.[/]\n")
            return 0
    except Exception as e:
        con.print(f"[yellow]Notice: Configuration written, but test ping returned warning: {e}[/]")
        con.print("[dim]You can test again anytime with:[/] [bold #00f0ff]kps ai config test[/]\n")
        return 0
