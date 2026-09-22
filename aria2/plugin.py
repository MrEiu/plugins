"""
Aria2 Plugin for Kapsel.
High-speed multi-threaded concurrent download accelerator powered by aria2c.
Default parameters: -s 16 (split), -x 16 (connections), -j 4 (parallel file jobs).
All comments and descriptions are in English.
"""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from kapsel.core.plugin.base import KapselPlugin, PluginManifest
from kapsel.core.plugin.context import PluginContext
from kapsel.storage.config import get_kapsel_dir
from kapsel.ui.banner import ensure_utf8_io

ensure_utf8_io()

DEFAULT_CONFIG: Dict[str, Any] = {
    "split": 16,
    "max_connection_per_server": 16,
    "max_concurrent_downloads": 4,
    "min_split_size": "1M",
    "dir": "",
}


def get_config_file() -> Path:
    """Returns the persistent path to ~/.kapsel/aria2_config.json."""
    return get_kapsel_dir() / "aria2_config.json"


def load_config() -> Dict[str, Any]:
    """Loads aria2 configuration or creates it with defaults."""
    cfg_file = get_config_file()
    if cfg_file.is_file():
        try:
            data = json.loads(cfg_file.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                merged = dict(DEFAULT_CONFIG)
                merged.update(data)
                return merged
        except Exception:
            pass
    return dict(DEFAULT_CONFIG)


def save_config(cfg: Dict[str, Any]) -> None:
    """Persists aria2 configuration to ~/.kapsel/aria2_config.json."""
    cfg_file = get_config_file()
    cfg_file.parent.mkdir(parents=True, exist_ok=True)
    cfg_file.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")


def resolve_aria2c_executable() -> Optional[str]:
    """
    Locates the aria2c binary across PATH, ~/.kapsel/bin, Scoop, WinGet, Homebrew, and system paths.
    """
    # 1. System PATH
    found = shutil.which("aria2c")
    if found:
        return found

    is_win = sys.platform == "win32"
    exe_name = "aria2c.exe" if is_win else "aria2c"

    # 2. Local Kapsel bin directory (~/.kapsel/bin)
    kapsel_bin = get_kapsel_dir() / "bin" / exe_name
    if kapsel_bin.exists():
        return str(kapsel_bin)

    # 3. Windows typical locations
    if is_win:
        user_home = Path(os.environ.get("USERPROFILE", Path.home()))
        candidates = [
            user_home / "scoop" / "shims" / exe_name,
            user_home / "scoop" / "apps" / "aria2" / "current" / exe_name,
            user_home / "AppData" / "Local" / "Microsoft" / "WinGet" / "Links" / exe_name,
            Path("C:/Program Files/aria2") / exe_name,
        ]
        for cand in candidates:
            if cand.is_file():
                return str(cand)
    else:
        # 4. Unix typical locations
        candidates = [
            Path("/opt/homebrew/bin") / exe_name,
            Path("/usr/local/bin") / exe_name,
            Path("/usr/bin") / exe_name,
        ]
        for cand in candidates:
            if cand.is_file():
                return str(cand)

    return None


class Aria2Plugin(KapselPlugin):
    """
    Kapsel Aria2 Plugin: Streamlined concurrent download accelerator.
    Wraps aria2c with pre-tuned concurrency flags (-s 16, -x 16, -j 4).
    """

    manifest = PluginManifest(
        id="aria2",
        name="Aria2",
        version="0.1.0",
        description="High-speed concurrent download accelerator powered by aria2c (-s 16, -x 16, -j 4).",
        author="Kapsel Team",
        homepage="https://github.com/MrEiu/plugins/tree/master/aria2",
        min_kapsel_version="0.1.0",
        dependencies=["aria2"],
        tags=["download", "aria2", "accelerator", "concurrency", "tools"],
    )

    def on_load(self, context: PluginContext) -> None:
        """Registers the 'aria2', 'down', and 'aria' commands under the 'kps' scope."""
        context.register_kps_command(
            name="aria2",
            handler=self.handle_aria2,
            help_text="Concurrent download accelerator powered by aria2c (-s 16, -x 16, -j 4)",
            usage="kps aria2 [urls/options] | kps aria2 config",
            scope="feature",
        )
        context.register_kps_command(
            name="down",
            handler=self.handle_aria2,
            help_text="Alias for 'kps aria2' concurrent download accelerator",
            usage="kps down [urls/options]",
            scope="feature",
        )
        context.register_kps_command(
            name="aria",
            handler=self.handle_aria2,
            help_text="Alias for 'kps aria2' concurrent download accelerator",
            usage="kps aria [urls/options]",
            scope="feature",
        )

    def handle_aria2(self, args: List[str], console: Optional[Console] = None) -> int:
        """
        Dispatches 'kps aria2' operations:
        - 'kps aria2 config [options]' -> Inspect or modify defaults
        - 'kps aria2 <url1> [url2...] [aria2_options]' -> Launch accelerated download
        """
        con = console or Console(legacy_windows=False)

        if not args or args[0].lower() in ("-h", "--help", "help"):
            return self._show_help(con)

        subcmd = args[0].lower()
        if subcmd == "config":
            return self._handle_config(args[1:], con)

        return self._execute_download(args, con)

    def _show_help(self, con: Console) -> int:
        """Displays concise usage guide."""
        cfg = load_config()
        con.print("\n[bold #00f0ff]⚡ Kapsel Aria2 Concurrent Download Accelerator[/]")
        con.print("[dim]Powered by aria2c with automatic multi-thread connection splitting & parallel file queue.[/]\n")

        con.print("[bold white]Usage:[/]")
        con.print("  [bold #a855f7]kps aria2 <url...>[/]                Download one or multiple URLs concurrently")
        con.print("  [bold #a855f7]kps down <url...>[/]                 Convenient short alias for 'kps aria2'")
        con.print("  [bold #a855f7]kps aria2 -i urls.txt[/]             Batch download from input file list")
        con.print("  [bold #a855f7]kps aria2 -o <filename> <url>[/]     Download and save as specific file name")
        con.print("  [bold #a855f7]kps aria2 -d <directory> <url>[/]    Save downloaded files to custom destination")
        con.print("  [bold #a855f7]kps aria2 config[/]                  Inspect current default concurrency parameters")
        con.print("  [bold #a855f7]kps aria2 config <key> <val>[/]      Modify default parameter (split, conn, jobs, dir)\n")

        con.print(f"[dim]Current Defaults:[/] [cyan]-s {cfg['split']}[/] (split)  "
                  f"[cyan]-x {cfg['max_connection_per_server']}[/] (conn/server)  "
                  f"[cyan]-j {cfg['max_concurrent_downloads']}[/] (parallel files)  "
                  f"[cyan]-c[/] (continue)\n")
        return 0

    def _handle_config(self, args: List[str], con: Console) -> int:
        """Manages configuration inspection and updates."""
        cfg = load_config()

        if not args:
            # Display current configuration table
            table = Table(title="⚡ Aria2 Default Parameters", box=None, header_style="bold #38bdf8")
            table.add_column("Parameter", style="cyan")
            table.add_column("Flag", style="bold white")
            table.add_column("Value", style="#10b981")
            table.add_column("Description", style="dim")

            table.add_row(
                "split",
                "-s",
                str(cfg["split"]),
                "Connections per file download",
            )
            table.add_row(
                "max_connection_per_server",
                "-x",
                str(cfg["max_connection_per_server"]),
                "Max connections to a single server",
            )
            table.add_row(
                "max_concurrent_downloads",
                "-j",
                str(cfg["max_concurrent_downloads"]),
                "Max simultaneous parallel file downloads",
            )
            table.add_row(
                "min_split_size",
                "-k",
                str(cfg["min_split_size"]),
                "Minimum file segment size for multi-thread splitting",
            )
            table.add_row(
                "dir",
                "-d",
                str(cfg["dir"]) if cfg["dir"] else "(current working directory)",
                "Default destination directory",
            )

            con.print()
            con.print(table)
            con.print("\n[dim]To change a setting:[/] [bold cyan]kps aria2 config split 32[/]  "
                      "[dim]or[/] [bold cyan]kps aria2 config -j 8[/]")
            con.print("[dim]To restore defaults:[/] [bold cyan]kps aria2 config reset[/]\n")
            return 0

        action = args[0].lower()
        if action == "reset":
            save_config(dict(DEFAULT_CONFIG))
            con.print("[bold #10b981]✔ Reset Aria2 configuration to defaults (-s 16, -x 16, -j 4).[/]")
            return 0

        if len(args) < 2:
            con.print(f"[bold #f43f5e]Error:[/] Missing value for parameter '{action}'.")
            con.print("[dim]Example: kps aria2 config split 32[/]")
            return 1

        val = args[1].strip()

        # Map aliases
        key_map = {
            "split": "split",
            "-s": "split",
            "s": "split",
            "conn": "max_connection_per_server",
            "max_conn": "max_connection_per_server",
            "-x": "max_connection_per_server",
            "x": "max_connection_per_server",
            "jobs": "max_concurrent_downloads",
            "concurrent": "max_concurrent_downloads",
            "-j": "max_concurrent_downloads",
            "j": "max_concurrent_downloads",
            "min_split": "min_split_size",
            "-k": "min_split_size",
            "k": "min_split_size",
            "dir": "dir",
            "-d": "dir",
            "d": "dir",
        }

        target_key = key_map.get(action)
        if not target_key:
            con.print(f"[bold #f43f5e]Error:[/] Unknown configuration parameter '{action}'.")
            con.print(f"[dim]Valid parameters: split (-s), conn (-x), jobs (-j), min_split (-k), dir (-d)[/]")
            return 1

        if target_key in ("split", "max_connection_per_server", "max_concurrent_downloads"):
            try:
                num_val = int(val)
                if num_val < 1:
                    raise ValueError
                cfg[target_key] = num_val
            except ValueError:
                con.print(f"[bold #f43f5e]Error:[/] Value for '{target_key}' must be a positive integer.")
                return 1
        else:
            cfg[target_key] = val

        save_config(cfg)
        con.print(f"[bold #10b981]✔ Updated '{target_key}' to:[/] [bold cyan]{cfg[target_key]}[/]")
        return 0

    def _execute_download(self, args: List[str], con: Console) -> int:
        """Constructs aria2c command with injected defaults and executes it."""
        aria2c_bin = resolve_aria2c_executable()
        if not aria2c_bin:
            con.print("\n[bold #f43f5e]Error:[/] [white]aria2c executable is not installed or not in PATH.[/]")
            con.print("[dim]Install it automatically using Kapsel package installer:[/] "
                      "[bold #00f0ff]kapsel add aria2[/]\n")
            return 1

        cfg = load_config()

        # Check existing flags in user args to avoid duplicates
        has_split = any(arg == "-s" or arg.startswith(("--split=", "--split")) for arg in args)
        has_conn = any(arg == "-x" or arg.startswith(("--max-connection-per-server=", "--max-connection-per-server")) for arg in args)
        has_jobs = any(arg == "-j" or arg.startswith(("--max-concurrent-downloads=", "--max-concurrent-downloads")) for arg in args)
        has_min_size = any(arg == "-k" or arg.startswith(("--min-split-size=", "--min-split-size")) for arg in args)
        has_continue = any(arg == "-c" or arg.startswith(("--continue=", "--continue")) for arg in args)
        has_dir = any(arg == "-d" or arg.startswith(("--dir=", "--dir")) for arg in args)

        cmd: List[str] = [aria2c_bin]

        # Inject configured defaults when not explicitly overridden
        if not has_split and cfg.get("split"):
            cmd.extend(["-s", str(cfg["split"])])
        if not has_conn and cfg.get("max_connection_per_server"):
            cmd.extend(["-x", str(cfg["max_connection_per_server"])])
        if not has_jobs and cfg.get("max_concurrent_downloads"):
            cmd.extend(["-j", str(cfg["max_concurrent_downloads"])])
        if not has_min_size and cfg.get("min_split_size"):
            cmd.extend(["-k", str(cfg["min_split_size"])])
        if not has_continue:
            cmd.append("-c")
        if not has_dir and cfg.get("dir"):
            cmd.extend(["-d", str(cfg["dir"])])

        # Append all user arguments
        cmd.extend(args)

        # Show brief non-intrusive status banner
        split_val = next((args[i + 1] for i, a in enumerate(args[:-1]) if a == "-s"), cfg["split"])
        conn_val = next((args[i + 1] for i, a in enumerate(args[:-1]) if a == "-x"), cfg["max_connection_per_server"])
        jobs_val = next((args[i + 1] for i, a in enumerate(args[:-1]) if a == "-j"), cfg["max_concurrent_downloads"])

        con.print(f"[dim]⚡ [bold #00f0ff]Aria2 Accelerator[/] "
                  f"[dim]| Threads/File: [bold cyan]{split_val}[/] "
                  f"| Conn/Server: [bold cyan]{conn_val}[/] "
                  f"| Parallel Files: [bold cyan]{jobs_val}[/][/]\n")

        try:
            # Interactive execution streaming aria2c progress directly
            res = subprocess.run(cmd)
            return res.returncode
        except KeyboardInterrupt:
            con.print("\n[yellow]Download interrupted by user.[/]")
            return 130
        except Exception as e:
            con.print(f"[bold #f43f5e]Failed to execute aria2c:[/] {e}")
            return 1
