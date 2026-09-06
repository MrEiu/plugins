"""
Init Plugin for Kapsel.
Bridges 'mise' (mise-en-place polyglot tool & runtime manager) to bootstrap project environments.
Exposes functional commands under the 'kps init' namespace.
All comments and descriptions are in English.
"""

import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.panel import Panel

from kapsel.core.plugin.base import KapselPlugin, PluginManifest
from kapsel.core.plugin.context import PluginContext
from kapsel.core.plugin.hooks import HookType
from kapsel.storage.config import get_kapsel_dir
from kapsel.ui.banner import ensure_utf8_io

ensure_utf8_io()


def _resolve_mise_executable() -> Optional[str]:
    """
    Locates the 'mise' CLI executable:
    1. System PATH ('mise' or 'mise.exe')
    2. Local Kapsel bin directory (~/.kapsel/bin/mise)
    3. Standard platform install locations (e.g. ~/.local/bin/mise, scoop, brew)
    """
    is_win = sys.platform == "win32"
    exe_name = "mise.exe" if is_win else "mise"

    # 1. System PATH
    p = shutil.which("mise") or shutil.which(exe_name)
    if p:
        return p

    # 2. Local Kapsel bin directory (~/.kapsel/bin)
    local_bin = get_kapsel_dir() / "bin" / exe_name
    if local_bin.exists():
        return str(local_bin)

    # 3. Standard platform directories
    home = Path.home()
    candidates: List[Path] = [
        home / ".local" / "bin" / exe_name,
        home / ".cargo" / "bin" / exe_name,
    ]

    if is_win:
        local_appdata = os.environ.get("LOCALAPPDATA")
        if local_appdata:
            candidates.append(Path(local_appdata) / "mise" / "bin" / exe_name)
        candidates.extend([
            home / "scoop" / "shims" / exe_name,
            Path("C:/ProgramData/chocolatey/bin") / exe_name,
        ])
    else:
        candidates.extend([
            Path("/usr/local/bin") / exe_name,
            Path("/home/linuxbrew/.linuxbrew/bin") / exe_name,
            Path("/opt/homebrew/bin") / exe_name,
        ])

    for cand in candidates:
        if cand.exists():
            return str(cand)

    return None


def _run_mise_command(args: List[str], console: Optional[Console] = None) -> int:
    """Executes a mise command, streaming output directly to the terminal."""
    con = console or Console(legacy_windows=False)
    mise_bin = _resolve_mise_executable()

    if not mise_bin:
        con.print("[bold #f43f5e]Error:[/] [white]mise (mise-en-place environment manager) is not found.[/]")
        con.print("[dim]Install mise via one of the following methods:[/]")
        if sys.platform == "win32":
            con.print("    [bold #00f0ff]winget install jdx.mise[/]     (Windows Package Manager)")
            con.print("    [bold #00f0ff]scoop install mise[/]          (Scoop)")
            con.print("    [bold #a855f7]irm https://mise.run | iex[/]   (PowerShell)\n")
        else:
            con.print("    [bold #00f0ff]curl https://mise.run | sh[/]     (Official Shell Installer)")
            con.print("    [bold #00f0ff]brew install mise[/]              (Homebrew)\n")
        return 1

    try:
        proc = subprocess.run([mise_bin] + args)
        return proc.returncode
    except Exception as e:
        con.print(f"[bold #f43f5e]Failed to execute mise {' '.join(args)}:[/] {e}")
        return 1


class InitPlugin(KapselPlugin):
    """
    Kapsel 'init' plugin integrating mise (mise-en-place).
    Provides project environment bootstrapping and runtime tool management under 'kps init'.
    """

    manifest = PluginManifest(
        id="init",
        name="Init",
        version="0.1.1",
        description="Project development environment and tool runtime initializer powered by mise.",
        author="Kapsel Team",
        homepage="https://github.com/kapsel-shell/kapsel-plugin-init",
        min_kapsel_version="0.1.0",
        dependencies=["mise"],
        tags=["env", "runtime", "installer", "tools", "mise", "init"],
    )

    def on_load(self, context: PluginContext) -> None:
        """Registers 'kps init' command and completion hooks."""
        context.register_kps_command(
            name="init",
            handler=self.handle_init,
            help_text="Bootstrap project dev environment and runtimes powered by mise",
            subcommands={
                "use": "Pin and install tool version into current project config (mise use)",
                "ls": "List installed and active tool versions (mise ls)",
                "list": "List installed and active tool versions (mise ls)",
                "current": "Show currently active tool versions in workspace (mise current)",
                "doctor": "Check and diagnose mise installation and environment (mise doctor)",
                "upgrade": "Upgrade outdated tool versions in current project (mise upgrade)",
                "run": "Run project task defined in mise.toml (mise run)",
            },
            usage="kps init [tool@version | use | ls | current | doctor | upgrade]",
            scope="feature",
        )

        # Hook dynamic completions for 'kps init <prefix>'
        context.register_hook(HookType.PROVIDE_COMPLETIONS, self.provide_completions)

    def handle_init(self, args: List[str], console: Optional[Console] = None) -> int:
        """
        Handles 'kps init' invocations:
        - No args: runs 'mise install' to bootstrap all tools declared in the current project
        - Specified tool (e.g. 'node@20'): runs 'mise install node@20'
        - Known subcommands ('use', 'ls', 'current', etc.): delegates to 'mise <subcommand>'
        """
        con = console or Console(legacy_windows=False)

        # 1. Bare 'kps init' -> Default action: 'mise install' (project environment bootstrap)
        if not args:
            con.print("[bold #00f0ff]🚀 Initializing project development environment via mise...[/]\n")
            return _run_mise_command(["install"], con)

        first_arg = args[0].lower()

        # 2. Help request
        if first_arg in ("-h", "--help", "help"):
            self._render_help(con)
            return 0

        # 3. Aliased / Known subcommands
        subcommand_aliases = {
            "list": "ls",
            "update": "upgrade",
        }
        known_subcommands = {
            "use", "ls", "current", "doctor", "upgrade",
            "run", "uninstall", "prune", "resettings", "version",
        }

        actual_subcmd = subcommand_aliases.get(first_arg, first_arg)
        if actual_subcmd in known_subcommands:
            return _run_mise_command([actual_subcmd] + args[1:], con)

        # 4. Direct tool install (e.g. 'kps init node@20' or 'kps init python')
        # Maps directly to 'mise install <tool>'
        return _run_mise_command(["install"] + args, con)

    def _render_help(self, console: Console) -> None:
        """Renders comprehensive, styled usage instructions for kps init."""
        content = (
            "[bold #00f0ff]Kapsel Project Environment Initializer (powered by mise)[/]\n"
            "[dim]Seamlessly sets up, installs, and manages multi-runtime dev environments.[/]\n\n"
            "[bold #10b981]Usage:[/]\n"
            "  [white]kps init[/]                           [dim]Bootstrap & install all tools defined in project (mise install)[/]\n"
            "  [white]kps init <tool>@<version>[/]           [dim]Install a specific tool runtime (e.g. node@20, go@1.22)[/]\n"
            "  [white]kps init use <tool>@<version>[/]       [dim]Pin and install a tool into current project config (mise use)[/]\n"
            "  [white]kps init ls | list[/]                  [dim]List installed and active tool runtimes (mise ls)[/]\n"
            "  [white]kps init current[/]                    [dim]Display active runtime versions in current directory[/]\n"
            "  [white]kps init doctor[/]                     [dim]Diagnose mise installation and environment health[/]\n"
            "  [white]kps init upgrade[/]                    [dim]Upgrade outdated tool versions in current project[/]\n"
            "  [white]kps init run <task>[/]                 [dim]Execute project task defined in mise.toml[/]\n\n"
            "[bold #f59e0b]Examples:[/]\n"
            "  [dim]$[/] [bold #00f0ff]kps init[/]                       # Installs all tools from .mise.toml / .tool-versions\n"
            "  [dim]$[/] [bold #00f0ff]kps init node@22[/]               # Installs Node.js v22\n"
            "  [dim]$[/] [bold #00f0ff]kps init use python@3.12[/]       # Sets Python 3.12 for current directory\n"
            "  [dim]$[/] [bold #00f0ff]kps init current[/]                # Check active versions\n"
        )
        console.print(Panel(content, title="[bold #00f0ff]kps init[/]", border_style="#0891b2"))

    def provide_completions(self, text_before_cursor: str) -> List[Dict[str, Any]]:
        """
        Provides dynamic auto-completions when typing 'kps init <prefix>'.
        Offers built-in subcommands and high-frequency tool runtimes.
        """
        stripped = text_before_cursor.lstrip()
        prefix_tag = "kps init"
        if not stripped.startswith(prefix_tag):
            return []

        after_cmd = stripped[len(prefix_tag):]
        if not after_cmd.startswith(" "):
            return []

        query = after_cmd.strip()
        q_lower = query.lower()

        # Candidates pool: subcommands + popular dev tools
        pool = [
            ("use", "Pin and install tool version (mise use)"),
            ("ls", "List installed & active tool versions (mise ls)"),
            ("current", "Show active versions in current directory"),
            ("doctor", "Check mise installation and environment health"),
            ("upgrade", "Upgrade outdated tools in current project"),
            ("run", "Run task defined in mise.toml"),
            ("node", "Node.js JavaScript runtime"),
            ("python", "Python interpreter runtime"),
            ("go", "Go programming language"),
            ("rust", "Rust programming language (cargo/rustc)"),
            ("java", "Java OpenJDK runtime"),
            ("deno", "Deno secure JavaScript runtime"),
            ("bun", "Bun fast all-in-one JavaScript runtime"),
            ("pnpm", "Fast, disk space efficient package manager"),
            ("terraform", "Terraform infrastructure as code tool"),
        ]

        candidates: List[Dict[str, Any]] = []
        for name, desc in pool:
            if name.startswith(q_lower):
                candidates.append({
                    "text": name,
                    "display": name,
                    "display_meta": f"🚀 {desc}",
                    "start_position": -len(query),
                })

        return candidates
