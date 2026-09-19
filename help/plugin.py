"""
Help Plugin for Kapsel.
Multi-tool query & interactive action router.
Dispatches command queries to cheat sheets, port inspectors, process managers,
DNS resolvers, HTTP clients, latency analyzers, and system specs.
All comments and docstrings are in English.
"""

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
from kapsel.ui.banner import ensure_utf8_io

ensure_utf8_io()

try:
    from .router import infer_help_intent
    from .install import install_recommended_tools
    from .actions.port import handle_port
    from .actions.process import handle_process, handle_kill
    from .actions.locate import handle_locate
    from .actions.dns import handle_dns
    from .actions.http import handle_http
    from .actions.stat import handle_stat
    from .actions.sysinfo import handle_sysinfo
    from .actions.cheat import handle_cheat, resolve_tldr_executable
except ImportError:
    from plugins.help.router import infer_help_intent
    from plugins.help.install import install_recommended_tools
    from plugins.help.actions.port import handle_port
    from plugins.help.actions.process import handle_process, handle_kill
    from plugins.help.actions.locate import handle_locate
    from plugins.help.actions.dns import handle_dns
    from plugins.help.actions.http import handle_http
    from plugins.help.actions.stat import handle_stat
    from plugins.help.actions.sysinfo import handle_sysinfo
    from plugins.help.actions.cheat import handle_cheat, resolve_tldr_executable


class HelpPlugin(KapselPlugin):
    """
    Kapsel 'help' plugin: Interactive multi-tool query & action router.
    """

    manifest = PluginManifest(
        id="help",
        name="Help",
        version="0.1.1",
        description="Multi-tool query & action router for command cheat sheets, ports, processes, DNS, HTTP, and system info.",
        author="Kapsel Team",
        homepage="https://github.com/MrEiu/plugins/tree/master/help",
        min_kapsel_version="0.1.0",
        dependencies=["tealdeer"],
        tags=["help", "cheatsheet", "tldr", "port", "process", "dns", "http", "sysinfo", "tools"],
    )

    def __init__(self) -> None:
        super().__init__()
        self._cached_page_names: Optional[List[str]] = None

    def on_load(self, context: PluginContext) -> None:
        """Registers the 'help' functional command under 'kps' scope and completion hook."""
        context.register_kps_command(
            name="help",
            handler=self.handle_help,
            help_text="Interactive multi-tool query & action router",
            usage="kps help [subcommand | auto-query] [options]",
            subcommands={
                "port": "Inspect port occupancy & kill occupying process (e.g. kps help port 8080)",
                "ps": "Inspect active processes & interactive termination (e.g. kps help ps node)",
                "kill": "Terminate process by PID (e.g. kps help kill 1234)",
                "which": "Locate binary executable path & copy/execute (e.g. kps help which python)",
                "where": "Alias for which",
                "dns": "Resolve DNS records, probe HTTP & reverse PTR (e.g. kps help dns github.com)",
                "http": "Execute HTTP/HTTPS request, retry & save response (e.g. kps help http url)",
                "stat": "Analyze HTTP latency timing waterfall (e.g. kps help stat url)",
                "sys": "Display system specifications and hardware info",
                "cheat": "Lookup CLI command cheat sheets and copy/execute examples",
                "install": "Check and install companion CLI tools (procs, xh, doggo, etc.)",
                "--update": "Update local tldr cheat sheet cache",
                "--list": "List all available command cheat sheets",
            },
            scope="feature",
        )

        context.register_hook(HookType.PROVIDE_COMPLETIONS, self.provide_completions)

    def handle_help(self, args: List[str], console: Optional[Console] = None) -> int:
        """
        Dispatches 'kps help' queries via smart intent routing.
        """
        con = console or Console(legacy_windows=False)

        # Handle tldr cache update / list flags
        if args and args[0] in ("-u", "--update"):
            tldr_bin = resolve_tldr_executable()
            if tldr_bin:
                con.print("[dim]Updating local tldr cache...[/dim]")
                return subprocess.run([tldr_bin, "--update"]).returncode
            con.print("[bold red]✖ tealdeer (tldr) is not installed.[/bold red]")
            return 1

        if args and args[0] in ("-l", "--list"):
            tldr_bin = resolve_tldr_executable()
            if tldr_bin:
                return subprocess.run([tldr_bin, "--list"]).returncode
            con.print("[bold red]✖ tealdeer (tldr) is not installed.[/bold red]")
            return 1

        action, forwarded_args = infer_help_intent(args)

        if action == "guide":
            return self._show_guide(con)
        elif action == "port":
            return handle_port(forwarded_args, con)
        elif action == "ps":
            return handle_process(forwarded_args, con)
        elif action == "kill":
            return handle_kill(forwarded_args, con)
        elif action == "which":
            return handle_locate(forwarded_args, con)
        elif action == "dns":
            return handle_dns(forwarded_args, con)
        elif action == "http":
            return handle_http(forwarded_args, con)
        elif action == "stat":
            return handle_stat(forwarded_args, con)
        elif action == "sys":
            return handle_sysinfo(forwarded_args, con)
        elif action == "install":
            install_recommended_tools(con)
            return 0
        else:
            return handle_cheat(forwarded_args, con)

    def _show_guide(self, con: Console) -> int:
        """Renders comprehensive user guide with smart auto-inference examples."""
        con.print("\n[bold #00f0ff]📖 Kapsel Help Router: Query & Action Workflow Engine[/bold #00f0ff]")
        con.print("[dim]Zero-friction auto-matching: just type 'kps help <anything>'[/dim]\n")

        con.print("[bold white]🎯 Smart Auto-Inference (Zero-Mental-Overhead):[/bold white]")
        con.print("  • [bold #a855f7]kps help 8080[/]               Inspect port :8080 and kill occupying process")
        con.print("  • [bold #a855f7]kps help github.com[/]         Resolve DNS, probe HTTP status, and reverse PTR")
        con.print("  • [bold #a855f7]kps help https://api.io[/]     Execute HTTP request, retry & save response")
        con.print("  • [bold #a855f7]kps help sys[/]                Display hardware specs, CPU, memory, and OS info")
        con.print("  • [bold #a855f7]kps help ps[/]                 View active process list with interactive Kill menu")
        con.print("  • [bold #a855f7]kps help tar[/]                View cheat sheet + copy/run examples + locate binary\n")

        con.print("[bold white]⚡ Explicit Subcommands:[/bold white]")
        con.print("  • [bold #38bdf8]kps help port <num>[/]          Check port listeners and terminate PID")
        con.print("  • [bold #38bdf8]kps help which <cmd>[/]         Discover all executable paths across PATH")
        con.print("  • [bold #38bdf8]kps help stat <url>[/]          Benchmark HTTP latency waterfall phases")
        con.print("  • [bold #38bdf8]kps help kill <pid>[/]          Terminate process by PID")
        con.print("  • [bold #38bdf8]kps help install[/]            Check and install companion tools (procs, xh, etc.)\n")

        con.print("[dim]💡 Looking for Kapsel system platform manual? Run:[/] [bold #00f0ff]kapsel help[/]\n")
        return 0

    def provide_completions(self, text_before_cursor: str) -> List[Dict[str, Any]]:
        """
        Provides dynamic auto-completions for subcommands and cached cheat sheet page names.
        """
        stripped = text_before_cursor.lstrip()
        prefix_tag = "kps help"
        if not stripped.startswith(prefix_tag):
            return []

        after_cmd = stripped[len(prefix_tag):]
        if not after_cmd.startswith(" "):
            return []

        query = after_cmd.strip()

        subcommands = [
            ("port", "Inspect port occupancy & kill process"),
            ("ps", "Inspect active processes & kill PID"),
            ("kill", "Terminate process by PID"),
            ("which", "Locate binary executable paths"),
            ("where", "Alias for which"),
            ("dns", "Resolve DNS records & probe HTTP"),
            ("http", "Execute HTTP/HTTPS request"),
            ("stat", "Analyze HTTP latency waterfall"),
            ("sys", "Display system specs & hardware info"),
            ("cheat", "Query command cheat sheets"),
            ("install", "Install companion CLI tools"),
            ("--update", "Update local tldr page cache"),
            ("--list", "List all available tldr pages"),
        ]

        candidates: List[Dict[str, Any]] = []
        q_lower = query.lower()

        # If user has only typed the first word after 'kps help'
        tokens = query.split()
        if len(tokens) <= 1:
            for sub, desc in subcommands:
                if sub.startswith(q_lower):
                    candidates.append({
                        "text": sub,
                        "display": sub,
                        "display_meta": desc,
                        "start_position": -len(query),
                    })

        # Also complete command names from tldr cache if not matching subcommands
        if len(candidates) < 10 and not query.startswith("-"):
            pages = self._get_cached_pages()
            for p_name in pages:
                if p_name.lower().startswith(q_lower):
                    candidates.append({
                        "text": p_name,
                        "display": p_name,
                        "display_meta": "📖 tldr cheat sheet",
                        "start_position": -len(query),
                    })
                    if len(candidates) >= 20:
                        break

        return candidates

    def _get_cached_pages(self) -> List[str]:
        """Lazy loads and caches available tldr command names."""
        if self._cached_page_names is not None:
            return self._cached_page_names

        tldr_bin = resolve_tldr_executable()
        if not tldr_bin:
            return []

        try:
            res = subprocess.run(
                [tldr_bin, "--list"],
                capture_output=True,
                text=True,
                errors="replace",
                timeout=2.0,
            )
            if res.returncode == 0 and res.stdout:
                self._cached_page_names = [line.strip() for line in res.stdout.splitlines() if line.strip()]
                return self._cached_page_names
        except Exception:
            pass

        return []


# Standard plugin alias
Plugin = HelpPlugin
