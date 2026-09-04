"""
Rec (Record / Snippet Manager) Plugin for Kapsel.
Bridges the 'pet' CLI tool to provide command snippet recording, interactive searching, and execution.
Exposes functional commands under the 'kps rec' namespace.
All comments and descriptions are in English.
"""

from pathlib import Path
import shutil
import subprocess
import sys
from typing import List, Optional

from rich.console import Console

from kapsel.core.plugin.base import KapselPlugin, PluginManifest
from kapsel.core.plugin.context import PluginContext
from kapsel.storage.config import get_kapsel_dir
from kapsel.ui.banner import ensure_utf8_io

ensure_utf8_io()


def _resolve_pet_executable() -> Optional[str]:
    """
    Locates the pet CLI executable.
    Checks system PATH first, then Kapsel local bin directory (~/.kapsel/bin).
    """
    # 1. System PATH
    pet_path = shutil.which("pet")
    if pet_path:
        return pet_path

    # 2. Local Kapsel bin directory (~/.kapsel/bin/pet.exe or pet)
    bin_dir = get_kapsel_dir() / "bin"
    local_pet = bin_dir / ("pet.exe" if sys.platform == "win32" else "pet")
    if local_pet.exists():
        return str(local_pet)

    return None


def _run_pet_command(args: List[str], console: Optional[Console] = None) -> int:
    """
    Executes a pet command forwarding interactive terminal I/O.
    Prompts the user with installation instructions if pet is not found.
    """
    con = console or Console(legacy_windows=False)
    pet_bin = _resolve_pet_executable()

    if not pet_bin:
        con.print("[bold #f43f5e]Error:[/] [white]pet (CLI snippet manager) is not installed.[/]")
        con.print("[dim]To install pet, run:[/] [bold #00f0ff]kapsel add rec[/]\n")
        return 1

    cmd = [pet_bin] + args
    try:
        # Stream process execution interactively in the terminal
        result = subprocess.run(cmd)
        return result.returncode
    except Exception as e:
        con.print(f"[bold #f43f5e]Failed to execute pet:[/] {e}")
        return 1


class RecPlugin(KapselPlugin):
    """
    Kapsel 'rec' plugin integrating the pet snippet manager.
    Provides snippet recording ('kps rec new <cmd>') and search/execution ('kps rec <query>').
    """

    manifest = PluginManifest(
        id="rec",
        name="Rec",
        version="0.1.0",
        description="Command snippet recorder and runner powered by pet CLI.",
        author="Kapsel Team",
        homepage="https://github.com/MrEiu/plugins/tree/master/rec",
        min_kapsel_version="0.1.0",
        dependencies=["pet"],
        tags=["snippets", "record", "productivity", "tools"],
    )

    def on_load(self, context: PluginContext) -> None:
        """Registers the 'rec' functional command under the 'kps' scope."""
        context.register_kps_command(
            name="rec",
            handler=self.handle_rec,
            help_text="Snippet manager: record ('rec new') or search & execute ('rec')",
            usage="kps rec [new|list|search|edit|sync] [query/options]",
            scope="feature",
        )

    def handle_rec(self, args: List[str], console: Optional[Console] = None) -> int:
        """
        Dispatches 'kps rec' subcommands:
        - 'kps rec new <cmd...>' -> pet new <cmd...>
        - 'kps rec list'         -> pet list
        - 'kps rec search <q>'   -> pet search [--query q]
        - 'kps rec edit'         -> pet edit
        - 'kps rec sync'         -> pet sync
        - 'kps rec [query...]'   -> pet exec [--query q]
        """
        if not args:
            # Bare 'kps rec' -> interactive snippet execution
            return _run_pet_command(["exec"], console)

        subcmd = args[0].lower()
        sub_args = args[1:]

        if subcmd == "new":
            # kps rec new [command...]
            # If user provided command string, pass it to pet new
            pet_args = ["new"]
            if sub_args:
                # pet new accepts: pet new COMMAND [flags]
                pet_args.append(" ".join(sub_args))
            return _run_pet_command(pet_args, console)

        elif subcmd in ("list", "ls"):
            # kps rec list [flags]
            return _run_pet_command(["list"] + sub_args, console)

        elif subcmd == "search":
            # kps rec search [query...]
            pet_args = ["search"]
            if sub_args:
                pet_args.extend(["-q", " ".join(sub_args)])
            return _run_pet_command(pet_args, console)

        elif subcmd == "edit":
            # kps rec edit
            return _run_pet_command(["edit"] + sub_args, console)

        elif subcmd == "sync":
            # kps rec sync
            return _run_pet_command(["sync"] + sub_args, console)

        elif subcmd in ("-h", "--help", "help"):
            # Show rec plugin help
            con = console or Console(legacy_windows=False)
            con.print("\n[bold #00f0ff]● Kapsel Rec Plugin (CLI Snippet Manager)[/]")
            con.print("[dim]Powered by 'pet' (https://github.com/knqyf263/pet)[/]\n")
            con.print("[bold white]Usage:[/]")
            con.print("  [bold #a855f7]kps rec[/]                      Interactive snippet search & execution (pet exec)")
            con.print("  [bold #a855f7]kps rec <query>[/]             Search snippet with initial query and run")
            con.print("  [bold #a855f7]kps rec new <command...>[/]     Record / save a new command snippet (pet new)")
            con.print("  [bold #a855f7]kps rec list[/]                 Display all stored command snippets (pet list)")
            con.print("  [bold #a855f7]kps rec search <query>[/]       Search snippets without executing (pet search)")
            con.print("  [bold #a855f7]kps rec edit[/]                 Edit the snippet configuration file (pet edit)")
            con.print("  [bold #a855f7]kps rec sync[/]                 Sync snippets to GitHub Gist / GitLab (pet sync)\n")
            return 0

        else:
            # Default: 'kps rec <query>' -> interactive execution with query filter
            query_str = " ".join(args)
            return _run_pet_command(["exec", "-q", query_str], console)
