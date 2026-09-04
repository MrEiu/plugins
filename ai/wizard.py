"""
Kapsel AI Plugin - Interactive Setup Wizard.
Guides users step-by-step through configuring LLM providers and models for aichat.
All comments and descriptions are in English.
"""

from getpass import getpass
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.panel import Panel
import yaml

from kapsel.storage.config import get_kapsel_dir
from kapsel.ui.banner import ensure_utf8_io

ensure_utf8_io()

# Predefined popular providers and default configurations
PROVIDERS = [
    {
        "id": "deepseek",
        "name": "DeepSeek (Official API)",
        "type": "openai-compatible",
        "client_name": "deepseek",
        "api_base": "https://api.deepseek.com/v1",
        "default_model": "deepseek-chat",
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "requires_key": True,
        "key_prompt": "Enter DeepSeek API Key (sk-...): ",
    },
    {
        "id": "ollama",
        "name": "Ollama (Local LLM - Free & Private, No API Key)",
        "type": "openai-compatible",
        "client_name": "ollama",
        "api_base": "http://localhost:11434/v1",
        "default_model": "deepseek-r1:latest",
        "models": ["deepseek-r1:latest", "llama3:latest", "qwen2.5:latest"],
        "requires_key": False,
        "key_prompt": "",
    },
    {
        "id": "siliconflow",
        "name": "SiliconFlow / 硅基流动 (High-speed Cloud Models)",
        "type": "openai-compatible",
        "client_name": "siliconflow",
        "api_base": "https://api.siliconflow.cn/v1",
        "default_model": "deepseek-ai/DeepSeek-V3",
        "models": ["deepseek-ai/DeepSeek-V3", "deepseek-ai/DeepSeek-R1", "Qwen/Qwen2.5-72B-Instruct"],
        "requires_key": True,
        "key_prompt": "Enter SiliconFlow API Key (sk-...): ",
    },
    {
        "id": "openai",
        "name": "OpenAI (Official API)",
        "type": "openai",
        "client_name": "openai",
        "api_base": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini",
        "models": ["gpt-4o-mini", "gpt-4o", "o1-mini"],
        "requires_key": True,
        "key_prompt": "Enter OpenAI API Key (sk-...): ",
    },
    {
        "id": "gemini",
        "name": "Google Gemini (Official OpenAI-Compatible Endpoint)",
        "type": "openai-compatible",
        "client_name": "gemini",
        "api_base": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "default_model": "gemini-2.0-flash",
        "models": ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"],
        "requires_key": True,
        "key_prompt": "Enter Google AI Studio API Key (AIzaSy...): ",
    },
    {
        "id": "claude",
        "name": "Anthropic Claude (Official API)",
        "type": "claude",
        "client_name": "claude",
        "api_base": "https://api.anthropic.com/v1",
        "default_model": "claude-3-5-sonnet-20241022",
        "models": ["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022"],
        "requires_key": True,
        "key_prompt": "Enter Anthropic API Key (sk-ant-...): ",
    },
    {
        "id": "custom",
        "name": "Custom OpenAI-Compatible (OneAPI, NewAPI, vLLM, etc.)",
        "type": "openai-compatible",
        "client_name": "custom",
        "api_base": "",
        "default_model": "",
        "models": [],
        "requires_key": True,
        "key_prompt": "Enter Custom API Key: ",
    },
]


def get_ai_config_dir() -> Path:
    """Returns the dedicated configuration directory for aichat managed by Kapsel."""
    cfg_dir = get_kapsel_dir() / "ai"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    return cfg_dir


def get_ai_config_file() -> Path:
    """Returns the path to config.yaml within Kapsel data directory."""
    return get_ai_config_dir() / "config.yaml"


def sync_to_system_config_dir(config_content: str) -> None:
    """
    Also copies configuration to the system-level aichat default directory
    so standalone aichat executions outside Kapsel can seamlessly use the same config.
    """
    try:
        if sys.platform == "win32":
            roaming = Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming"))
            target_dir = roaming / "aichat"
        elif sys.platform == "darwin":
            target_dir = Path.home() / "Library/Application Support/aichat"
        else:
            target_dir = Path.home() / ".config/aichat"

        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "config.yaml").write_text(config_content, encoding="utf-8")
    except Exception:
        pass


def run_ai_setup_wizard(console: Optional[Console] = None) -> int:
    """
    Runs an interactive terminal wizard to configure an AI provider for aichat.
    """
    con = console or Console(legacy_windows=False)

    menu_lines = ["[bold #00f0ff]Select an AI model provider to configure:[/]\n"]
    for idx, prov in enumerate(PROVIDERS, start=1):
        menu_lines.append(f"  [bold #a855f7][{idx}][/] [white]{prov['name']}[/]")

    con.print(Panel("\n".join(menu_lines), title="[bold #00f0ff]🤖 Kapsel AI Setup Wizard (kps ai init)[/]", border_style="#0891b2"))

    # 1. Choice of provider
    try:
        raw_choice = input("Enter choice [1-7] (default: 1): ").strip()
        choice_idx = int(raw_choice) - 1 if raw_choice else 0
        if not (0 <= choice_idx < len(PROVIDERS)):
            con.print("[bold #f43f5e]Invalid selection. Defaulting to DeepSeek.[/]")
            choice_idx = 0
    except (ValueError, KeyboardInterrupt):
        con.print("\n[dim]Setup aborted.[/]")
        return 1

    selected = PROVIDERS[choice_idx]
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
        try:
            # Masked password input
            api_key = getpass(selected["key_prompt"]).strip()
            if not api_key:
                con.print("[yellow]Warning: Empty API key provided. Some requests may be rejected by the provider.[/]")
        except (KeyboardInterrupt, EOFError):
            con.print("\n[dim]Setup aborted.[/]")
            return 1
    else:
        con.print("[dim]No API key required for local Ollama.[/]")

    # 4. Model Selection
    default_model = selected["default_model"]
    if selected["id"] == "custom":
        model_name = input("Enter Model Name (e.g. gpt-3.5-turbo, qwen-max): ").strip() or "gpt-3.5-turbo"
    else:
        con.print(f"[dim]Suggested models:[/] {', '.join(selected['models'])}")
        model_input = input(f"Default Model [{default_model}]: ").strip()
        model_name = model_input if model_input else default_model

    client_name = selected["client_name"]

    # 5. Build configuration structure
    client_entry: Dict[str, Any] = {
        "type": selected["type"],
        "name": client_name,
    }
    if api_base:
        client_entry["api_base"] = api_base
    if api_key:
        client_entry["api_key"] = api_key
    if selected["models"]:
        client_entry["models"] = [{"name": m} for m in selected["models"]]

    config_data: Dict[str, Any] = {
        "model": f"{client_name}:{model_name}",
        "stream": True,
        "save": False,
        "keybindings": "emacs",
        "wrap": "auto",
        "wrap_code": False,
        "highlight": True,
        "clients": [client_entry],
    }

    yaml_text = yaml.dump(config_data, sort_keys=False, allow_unicode=True)

    # 6. Save configuration to Kapsel and system directories
    target_file = get_ai_config_file()
    target_file.write_text(yaml_text, encoding="utf-8")
    sync_to_system_config_dir(yaml_text)

    con.print(f"\n[bold #10b981]✔ Configuration successfully saved![/]")
    con.print(f"[dim]Kapsel config file: {target_file}[/]")

    # 7. Quick verification test
    con.print("\n[dim]Testing configuration with local aichat...[/]")
    test_res = verify_ai_configuration(console=con)
    if test_res == 0:
        con.print("[bold #10b981]✨ AI setup complete! You can now use:[/] [bold #00f0ff]kps ai <question>[/]\n")
    else:
        con.print("[yellow]Notice: Configuration written, but model connection test reported warnings. Please verify your network or API Key.[/]\n")

    return 0


def verify_ai_configuration(console: Optional[Console] = None) -> int:
    """Verifies that aichat loads the current configuration correctly."""
    from .plugin import _resolve_aichat_executable
    aichat_bin = _resolve_aichat_executable()
    if not aichat_bin:
        return 1

    env = os.environ.copy()
    env["AICHAT_CONFIG_DIR"] = str(get_ai_config_dir())

    try:
        res = subprocess.run(
            [aichat_bin, "--dry-run", "test"],
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5.0,
        )
        return res.returncode
    except Exception:
        return 1
