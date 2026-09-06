"""
Installer for ai plugin.
Ensures the official 'openai' Python SDK is available for the native AI engine.
All comments and descriptions are in English.
"""

from pathlib import Path
import subprocess
import sys
from rich.console import Console

from .config import load_ai_config


def install(console: Console, bin_dir: Path) -> bool:
    """
    Verifies that the native AI engine dependencies are ready.
    Ensures 'openai' Python package is installed and informs the user.
    """
    bin_dir.mkdir(parents=True, exist_ok=True)

    try:
        import openai  # noqa: F401
        has_openai = True
    except ImportError:
        has_openai = False

    if not has_openai:
        console.print("[bold #00f0ff]📦 Installing official 'openai' Python SDK...[/]")
        try:
            res = subprocess.run(
                [sys.executable, "-m", "pip", "install", "openai>=1.0.0"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=120,
            )
            if res.returncode == 0:
                console.print("[bold #10b981]✔ 'openai' Python SDK installed successfully![/]")
                has_openai = True
            else:
                console.print("[yellow]Warning: Could not automatically install 'openai'. Please run: pip install openai>=1.0.0[/]")
        except Exception as e:
            console.print(f"[yellow]Warning: Error installing 'openai': {e}[/]")

    if has_openai:
        console.print("[bold #10b981]✔ Kapsel native AI engine is ready.[/]")

    # Check if configured
    if not load_ai_config():
        console.print("[dim]Run '[bold #00f0ff]kps ai init[/]' to configure your model provider (DeepSeek, SiliconFlow, Ollama, Gemini, OpenAI).[/]\n")

    return True
