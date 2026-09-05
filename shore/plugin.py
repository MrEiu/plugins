"""
Shore (Mirror Source Switcher) Plugin for Kapsel.
Bridges 'chsrc' (Change Source) to provide fast, cross-platform mirror switching
for programming languages, package managers, and operating systems.
Exposes functional commands under the 'kps shore' namespace.
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
from rich.table import Table

from kapsel.core.plugin.base import KapselPlugin, PluginManifest
from kapsel.core.plugin.context import PluginContext
from kapsel.core.plugin.hooks import HookType
from kapsel.storage.config import get_kapsel_dir
from kapsel.ui.banner import ensure_utf8_io

ensure_utf8_io()

# Common supported dishes across languages, package managers, and tools
COMMON_DISHES: Dict[str, str] = {
    # Python ecosystem
    "python": "Python / PyPI package index",
    "pip": "Python pip package installer",
    "uv": "Fast Python package and project manager (Astral uv)",
    "poetry": "Python packaging and dependency management",
    "pdm": "Modern Python package and dependency manager",
    "rye": "Python package management tool",
    # JavaScript / Node.js ecosystem
    "npm": "Node.js package manager",
    "yarn": "Fast, reliable, and secure dependency management",
    "pnpm": "Fast, disk space efficient package manager",
    "bun": "All-in-one JavaScript runtime & package manager",
    "node": "Node.js binary distributions",
    "nvm": "Node Version Manager",
    # Rust & Go ecosystem
    "cargo": "Rust package manager and crates.io registry",
    "rustup": "Rust toolchain installer and updater",
    "go": "Go module proxy and sumdb",
    # Container & System Package Managers
    "docker": "Docker daemon registry mirror",
    "brew": "Homebrew package manager (bottles & git repos)",
    "scoop": "Scoop command-line installer for Windows",
    "winget": "Windows Package Manager repository",
    "conda": "Anaconda / Miniconda package repositories",
    # JVM & .NET ecosystem
    "maven": "Apache Maven central repository",
    "gradle": "Gradle build tool repository",
    "nuget": ".NET NuGet package feed",
    # Mobile & Other languages
    "flutter": "Flutter SDK and pub packages",
    "dart": "Dart pub package repository",
    "ruby": "RubyGems package repository",
    "composer": "PHP Composer repository (Packagist)",
    "cpan": "Perl CPAN package archive",
    # Linux distributions
    "ubuntu": "Ubuntu Linux APT package archives",
    "debian": "Debian Linux APT package archives",
    "arch": "Arch Linux pacman package mirrors",
    "fedora": "Fedora Linux RPM repositories",
    "alpine": "Alpine Linux apk package mirrors",
}

COMMON_MIRRORS: Dict[str, str] = {
    "first": "Fastest mirror benchmarked by the upstream maintainer team",
    "tuna": "Tsinghua University Open Source Mirror (TUNA)",
    "aliyun": "Alibaba Cloud Open Source Mirror",
    "ustc": "University of Science and Technology of China (USTC)",
    "tencent": "Tencent Cloud Public Mirror",
    "huawei": "Huawei Cloud Open Source Mirror",
    "163": "NetEase Open Source Mirror",
    "bfsu": "Beijing Foreign Studies University Mirror",
    "sjtu": "Shanghai Jiao Tong University Mirror",
}


def _resolve_chsrc_executable() -> Optional[str]:
    """
    Locates the chsrc executable across known system and sandbox paths:
    1. System PATH
    2. Local Kapsel bin directory (~/.kapsel/bin/chsrc.exe or chsrc)
    3. Scoop shims and apps directory
    4. WinGet links directory
    5. Cargo bin directory
    """
    # 1. System PATH
    p = shutil.which("chsrc")
    if p:
        return p

    is_win = sys.platform == "win32"

    # 2. Local Kapsel bin directory (~/.kapsel/bin)
    bin_dir = get_kapsel_dir() / "bin"
    local_bin = bin_dir / ("chsrc.exe" if is_win else "chsrc")
    if local_bin.exists():
        return str(local_bin)

    # 3. Windows-specific user locations (Scoop, WinGet, Cargo)
    if is_win:
        user_home = Path(os.environ.get("USERPROFILE", Path.home()))
        candidates = [
            user_home / "scoop/shims/chsrc.exe",
            user_home / "scoop/apps/chsrc/current/chsrc.exe",
            user_home / "AppData/Local/Microsoft/WinGet/Links/chsrc.exe",
            user_home / ".cargo/bin/chsrc.exe",
        ]
        for c in candidates:
            if c.exists():
                return str(c)

    return None


def _run_chsrc(args: List[str], console: Optional[Console] = None) -> int:
    """Executes chsrc with forwarded arguments, streaming stdout/stderr."""
    con = console or Console(legacy_windows=False)
    chsrc_bin = _resolve_chsrc_executable()

    if not chsrc_bin:
        con.print("[bold #f43f5e]Error:[/] [white]chsrc (Change Source CLI) executable not found.[/]")
        con.print("[dim]To install chsrc automatically, run:[/] [bold #00f0ff]kapsel add shore[/]\n")
        return 1

    try:
        proc = subprocess.run([chsrc_bin] + args)
        return proc.returncode
    except KeyboardInterrupt:
        con.print("\n[dim]Aborted.[/]")
        return 130
    except Exception as e:
        con.print(f"[bold #f43f5e]Execution error:[/] {e}")
        return 1


class ShorePlugin(KapselPlugin):
    """
    Shore (Mirror Source Switcher) Plugin for Kapsel.
    Provides fast, intelligent mirror switching across programming languages,
    package managers, and operating systems powered by chsrc.
    """

    manifest = PluginManifest(
        id="shore",
        name="Shore",
        version="0.1.0",
        description="Fast intelligent mirror source switcher powered by chsrc.",
        author="Kapsel Team",
        homepage="https://github.com/MrEiu/plugins/tree/master/shore",
        min_kapsel_version="0.1.0",
        tags=["mirror", "chsrc", "source", "network", "package-manager"],
    )

    def on_load(self, context: PluginContext) -> None:
        """Registers 'kps shore' commands and completion hooks."""
        context.register_kps_command(
            name="shore",
            handler=self.handle_shore,
            help_text="Fast intelligent mirror source switcher (powered by chsrc)",
            subcommands={
                "set": "Auto-benchmark and switch to the fastest mirror source",
                "get": "Display current active mirror source configuration",
                "reset": "Reset back to official default upstream source",
                "measure": "Speed-test all available mirror sources",
                "list": "List supported languages, systems, software, or mirrors",
            },
            usage="kps shore [set|get|reset|measure|list] <dish> [mirror]",
            scope="feature",
        )

        # Register dynamic autocompletion for dishes and mirrors
        context.register_hook(HookType.PROVIDE_COMPLETIONS, self.provide_completions)

    def handle_shore(self, args: List[str], console: Optional[Console] = None) -> int:
        """
        Dispatches 'kps shore' commands:
        - 'kps shore' (bare)                     -> Display sleek guidance dashboard
        - 'kps shore set <dish> [mirror]'        -> Switch mirror (auto fastest or specific)
        - 'kps shore <dish>' (shorthand)         -> Auto-switch <dish> to fastest mirror
        - 'kps shore get <dish>'                 -> View active mirror for <dish>
        - 'kps shore reset <dish>'               -> Reset <dish> to official upstream
        - 'kps shore measure <dish>'             -> Benchmark all mirrors for <dish>
        - 'kps shore list [os|lang|ware|mirror]' -> List supported dishes/mirrors
        """
        con = console or Console(legacy_windows=False)

        if not args or args in (["-h"], ["--help"]):
            self._render_help_dashboard(con)
            return 0

        first = args[0].lower()

        # Shorthand support: 'kps shore py' or 'kps shore npm' directly triggers auto-set
        if first in COMMON_DISHES and len(args) == 1:
            con.print(f"[bold #00f0ff]⚡ Shorthand detected:[/] Switching [white]{first}[/] to fastest mirror...")
            return _run_chsrc(["set", first], con)

        if first in ("measure", "m", "speed", "cesu"):
            forward_args = ["measure"] + args[1:]
            return _run_chsrc(forward_args, con)

        if first in ("ls", "list", "l"):
            forward_args = ["list"] + args[1:]
            return _run_chsrc(forward_args, con)

        if first in ("s", "set"):
            forward_args = ["set"] + args[1:]
            return _run_chsrc(forward_args, con)

        if first in ("g", "get"):
            forward_args = ["get"] + args[1:]
            return _run_chsrc(forward_args, con)

        if first in ("reset", "r"):
            forward_args = ["reset"] + args[1:]
            return _run_chsrc(forward_args, con)

        # Forward any extra flags or raw commands directly to chsrc
        return _run_chsrc(args, con)

    def _render_help_dashboard(self, con: Console) -> None:
        """Renders an elegant terminal guide for kps shore."""
        msg = (
            "[bold #00f0ff]🌊 Kapsel Shore (Fast Mirror Source Switcher)[/]\n"
            "[dim]Powered by chsrc (Change Source) | https://github.com/RubyMetric/chsrc[/]\n\n"
            "[bold white]Usage:[/]\n"
            "  [bold #a855f7]kps shore set <dish>[/]              Auto-speedtest & switch to the fastest mirror\n"
            "  [bold #a855f7]kps shore set <dish> <mirror>[/]     Switch to specific mirror (e.g. tuna, aliyun, ustc)\n"
            "  [bold #a855f7]kps shore <dish>[/]                  Quick shorthand for 'kps shore set <dish>'\n"
            "  [bold #a855f7]kps shore get <dish>[/]              Inspect active mirror configuration for dish\n"
            "  [bold #a855f7]kps shore reset <dish>[/]            Restore upstream official default source\n"
            "  [bold #a855f7]kps shore measure <dish>[/]          Speed-test and rank all mirrors for dish\n"
            "  [bold #a855f7]kps shore list [lang|os|ware][/]     List all supported targets or mirror hubs\n\n"
            "[bold white]Popular Dishes:[/]\n"
            "  [#10b981]Python:[/] py, pip, uv, poetry, pdm, conda\n"
            "  [#10b981]Node/JS:[/] npm, pnpm, yarn, bun, node\n"
            "  [#10b981]System:[/] brew, scoop, winget, docker, apt, pacman\n"
            "  [#10b981]Rust/Go:[/] cargo, rustup, go\n\n"
            "[bold white]Popular Mirrors:[/] tuna (Tsinghua), aliyun, ustc, tencent, huawei, first"
        )
        con.print(Panel(msg, title="[bold #00f0ff]⛵ Shore Mirror Manager[/]", border_style="#0891b2", expand=False))

    def provide_completions(self, text_before_cursor: str) -> List[Dict[str, Any]]:
        """
        Provides rich autocompletions for:
        - kps shore <subcommand>
        - kps shore set <dish>
        - kps shore set <dish> <mirror>
        - kps shore <dish> (direct shorthand)
        """
        stripped = text_before_cursor.lstrip()
        prefix = "kps shore"
        if not stripped.startswith(prefix):
            return []

        after = stripped[len(prefix):]
        if not after.startswith(" "):
            return []

        parts = after.strip().split()
        ends_with_space = after.endswith(" ")

        # 1. kps shore <query>
        if (len(parts) == 0) or (len(parts) == 1 and not ends_with_space):
            curr = parts[0].lower() if parts else ""
            cands = []
            # Subcommands
            for sub, desc in [
                ("set", "Auto-benchmark and switch to the fastest mirror"),
                ("get", "Inspect active mirror source configuration"),
                ("reset", "Restore upstream official default source"),
                ("measure", "Speed-test all available mirrors"),
                ("list", "List supported targets or mirror hubs"),
            ]:
                if sub.startswith(curr):
                    cands.append({"text": sub, "display": sub, "display_meta": f"🔹 {desc}"})

            # Also offer top dishes for direct one-click shorthand
            for dish, desc in list(COMMON_DISHES.items())[:10]:
                if dish.startswith(curr) and dish not in ("set", "get", "reset", "measure", "list"):
                    cands.append({"text": dish, "display": dish, "display_meta": f"⚡ Auto-switch: {desc}"})
            return cands

        # 2. kps shore (set|get|reset|measure) <dish>
        subcmd = parts[0].lower()
        if subcmd in ("set", "get", "reset", "measure", "m", "s", "g", "r"):
            if (len(parts) == 1 and ends_with_space) or (len(parts) == 2 and not ends_with_space):
                curr = parts[1].lower() if len(parts) == 2 else ""
                cands = []
                for dish, desc in COMMON_DISHES.items():
                    if dish.startswith(curr):
                        cands.append({"text": dish, "display": dish, "display_meta": f"📦 {desc}"})
                return cands

            # 3. kps shore set <dish> <mirror>
            if subcmd in ("set", "s"):
                if (len(parts) == 2 and ends_with_space) or (len(parts) == 3 and not ends_with_space):
                    curr = parts[2].lower() if len(parts) == 3 else ""
                    cands = []
                    for mirror, desc in COMMON_MIRRORS.items():
                        if mirror.startswith(curr):
                            cands.append({"text": mirror, "display": mirror, "display_meta": f"🌐 {desc}"})
                    return cands

        # 4. kps shore list <target>
        if subcmd in ("list", "ls", "l"):
            if (len(parts) == 1 and ends_with_space) or (len(parts) == 2 and not ends_with_space):
                curr = parts[1].lower() if len(parts) == 2 else ""
                cands = []
                for cat, desc in [
                    ("mirror", "List all known mirror providers"),
                    ("dish", "List all supported tools and package managers"),
                    ("lang", "List programming language dishes"),
                    ("os", "List operating system dishes"),
                    ("ware", "List software / package manager dishes"),
                ]:
                    if cat.startswith(curr):
                        cands.append({"text": cat, "display": cat, "display_meta": f"📋 {desc}"})
                return cands

        return []
