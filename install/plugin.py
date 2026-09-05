"""
Install Plugin for Kapsel.
Bridges meta-package-manager (mpm) to provide unified cross-platform package operations.
Features intelligent package manager auto-detection, platform-adaptive priority ordering,
and an independent persistent configuration file.
All comments and descriptions are in English.
"""

from pathlib import Path
import platform
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional
import yaml
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from kapsel.core.plugin.base import KapselPlugin, PluginManifest
from kapsel.core.plugin.context import PluginContext
from kapsel.storage.config import get_kapsel_dir


# ------------------------------------------------------------------------------
# Dynamic Configuration Loader for Package Managers & Platform Templates
# ------------------------------------------------------------------------------
def _get_defaults_file() -> Path:
    """Returns the path to defaults.yaml packaged with this plugin."""
    return Path(__file__).parent / "defaults.yaml"


_DEFAULTS_CACHE: Optional[Dict[str, Any]] = None


def _load_defaults() -> Dict[str, Any]:
    """Loads manager definitions and platform priority templates from defaults.yaml."""
    global _DEFAULTS_CACHE
    if _DEFAULTS_CACHE is not None:
        return _DEFAULTS_CACHE

    defaults_path = _get_defaults_file()
    if defaults_path.is_file():
        try:
            with open(defaults_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if isinstance(data, dict):
                    _DEFAULTS_CACHE = data
                    return data
        except Exception:
            pass

    fallback = {"managers": {}, "platforms": {}}
    _DEFAULTS_CACHE = fallback
    return fallback


def get_manager_binaries() -> Dict[str, tuple[str, ...]]:
    """Returns dictionary mapping manager ID to executable binary names from defaults.yaml."""
    raw = _load_defaults().get("managers", {})
    return {k: tuple(v) if isinstance(v, list) else (v,) for k, v in raw.items()}


def get_platform_templates() -> Dict[str, List[str]]:
    """Returns platform priority templates mapping from defaults.yaml."""
    return _load_defaults().get("platforms", {})


# Module-level references for fast lookup and backward compatibility
MANAGER_BINARIES: Dict[str, tuple[str, ...]] = get_manager_binaries()
PLATFORM_PRIORITY_TEMPLATES: Dict[str, List[str]] = get_platform_templates()


def _get_current_platform_key() -> str:
    """Identifies the current platform / Linux distribution family."""
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    if sys.platform.startswith("linux"):
        os_release = Path("/etc/os-release")
        if os_release.is_file():
            try:
                content = os_release.read_text(encoding="utf-8", errors="ignore").lower()
                distro_rules: Dict[str, List[str]] = _load_defaults().get("distro_patterns", {})
                for distro_key, patterns in distro_rules.items():
                    if any(p in content for p in patterns):
                        return distro_key
            except Exception:
                pass
        return "linux"
    return "linux"


def _detect_installed_managers() -> List[str]:
    """Scans system PATH for installed, recognized package managers."""
    installed: List[str] = []
    for mid, bins in MANAGER_BINARIES.items():
        if any(shutil.which(b) for b in bins):
            installed.append(mid)
    return installed


def _sort_managers_by_platform(detected: List[str], platform_key: Optional[str] = None) -> List[str]:
    """
    Sorts a list of detected managers based on the platform's priority template.
    Managers in the template come first (in template order), and any additional detected
    managers follow sequentially.
    """
    key = platform_key or _get_current_platform_key()
    template = PLATFORM_PRIORITY_TEMPLATES.get(key, PLATFORM_PRIORITY_TEMPLATES.get("linux", []))
    ordered: List[str] = []

    # 1. Add detected managers that exist in template, preserving template priority order
    for mid in template:
        if mid in detected and mid not in ordered:
            ordered.append(mid)

    # 2. Append remaining detected managers
    for mid in detected:
        if mid not in ordered:
            ordered.append(mid)

    return ordered


def _resolve_mpm_executable() -> Optional[List[str]]:
    """
    Locates the meta-package-manager (mpm) CLI executable.
    Checks PATH first, then Kapsel local bin directory, then python module.
    """
    # 1. System PATH
    mpm_path = shutil.which("mpm")
    if mpm_path:
        return [mpm_path]

    # 2. Local Kapsel bin directory (~/.kapsel/bin/mpm)
    local_bin = get_kapsel_dir() / "bin" / ("mpm.exe" if sys.platform == "win32" else "mpm")
    if local_bin.exists():
        return [str(local_bin)]

    # 3. Python environment module (pip)
    try:
        res = subprocess.run(
            [sys.executable, "-m", "meta_package_manager", "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,
        )
        if res.returncode == 0:
            return [sys.executable, "-m", "meta_package_manager"]
    except Exception:
        pass

    return None


def _run_mpm_command(subcmd: str, args: List[str], console: Optional[Console] = None) -> int:
    """
    Executes an MPM subcommand with forwarded arguments.
    Prompts the user with installation methods if mpm is not found.
    """
    con = console or Console(legacy_windows=False)
    mpm_exec = _resolve_mpm_executable()

    if not mpm_exec:
        con.print("[bold #f43f5e]Error:[/] [white]meta-package-manager (mpm) is not installed.[/]")
        con.print("[dim]Install it via one of the following methods:[/]")
        if sys.platform == "win32":
            con.print("    [bold #00f0ff]scoop install main/meta-package-manager[/]  (Scoop)")
        else:
            con.print("    [bold #00f0ff]brew install meta-package-manager[/]  (Homebrew)")
        con.print("    [bold #a855f7]pip install meta-package-manager[/]  (Python pip)\n")
        return 1

    cmd = mpm_exec + [subcmd] + args
    try:
        # Stream process execution interactively to the terminal
        result = subprocess.run(cmd)
        return result.returncode
    except Exception as e:
        con.print(f"[bold #f43f5e]Failed to execute mpm {subcmd}:[/] {e}")
        return 1


class InstallPlugin(KapselPlugin):
    """
    Kapsel 'install' plugin integrating meta-package-manager.
    Provides unified package installation, updating, searching, and syncing under the 'kps' scope
    with automatic platform detection and persistent manager priority order.
    """

    manifest = PluginManifest(
        id="install",
        name="Install",
        version="0.2.0",
        description="Unified cross-platform package installer powered by meta-package-manager (mpm) with adaptive manager priority.",
        author="Kapsel Team",
        homepage="https://github.com/kapsel-shell/kapsel-plugin-install",
        min_kapsel_version="0.1.0",
        dependencies=["meta-package-manager"],
        tags=["package-manager", "installer", "tools"],
    )

    def __init__(self) -> None:
        super().__init__()
        self.context: Optional[PluginContext] = None
        self._cached_config: Optional[Dict[str, Any]] = None

    def on_load(self, context: PluginContext) -> None:
        """Registers mpm-backed functional commands under the 'kps' scope."""
        self.context = context

        # 1. kps install <package>
        context.register_kps_command(
            name="install",
            handler=self.handle_install,
            help_text="Install package(s) across systems using meta-package-manager",
            usage="kps install <package_name> [options]",
            subcommands={
                "--order": "Show package manager priority order",
                "--detect": "Rescan system and update package manager priorities",
                "--config": "Show path to independent package manager configuration",
            },
            scope="feature",
        )

        # 2. kps update [package]
        context.register_kps_command(
            name="update",
            handler=self.handle_update,
            help_text="Update installed packages across package managers",
            usage="kps update [package_name] [options]",
            scope="feature",
        )

        # 3. kps search <query>
        context.register_kps_command(
            name="search",
            handler=self.handle_search,
            help_text="Search for packages across package managers",
            usage="kps search <query> [options]",
            scope="feature",
        )

        # 4. kps sync -mpm [options]
        context.register_kps_command(
            name="sync",
            handler=self.handle_sync,
            help_text="Synchronize package configurations (use -mpm for meta-package-manager)",
            subcommands={
                "-mpm": "Sync package manager configurations via mpm",
                "--mpm": "Sync package manager configurations via mpm",
            },
            usage="kps sync -mpm [options]",
            scope="feature",
        )

    # --------------------------------------------------------------------------
    # Configuration Management
    # --------------------------------------------------------------------------

    def get_config_path(self) -> Path:
        """Returns the path to the independent config.yaml file."""
        ctx = getattr(self, "context", None)
        if ctx and hasattr(ctx, "plugin_data_dir") and ctx.plugin_data_dir:
            target_dir = ctx.plugin_data_dir
        else:
            target_dir = get_kapsel_dir() / "plugins_data" / "install"
        target_dir.mkdir(parents=True, exist_ok=True)
        return target_dir / "config.yaml"

    def load_config(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Loads the configuration from disk.
        If missing or corrupted, automatically triggers auto-detection and saves a new config.
        """
        if self._cached_config and not force_refresh:
            return self._cached_config

        config_path = self.get_config_path()
        if config_path.is_file() and not force_refresh:
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    if isinstance(data, dict) and "managers" in data:
                        self._cached_config = data
                        return data
            except Exception:
                pass

        # Generate default config on first run or forced refresh
        conf = self.generate_default_config()
        self.save_config(conf)
        self._cached_config = conf
        return conf

    def generate_default_config(self) -> Dict[str, Any]:
        """Runs automatic detection and creates the default configuration dictionary."""
        plat_key = _get_current_platform_key()
        detected = _detect_installed_managers()
        sorted_managers = _sort_managers_by_platform(detected, plat_key)

        # Default disabled managers defined in defaults.yaml (e.g. raw pip to avoid global pollution)
        default_disabled = _load_defaults().get("default_disabled", ["pip"])
        disabled: List[str] = []
        for m in default_disabled:
            if m in sorted_managers:
                sorted_managers.remove(m)
                disabled.append(m)

        return {
            "version": "1.0",
            "platform": plat_key,
            "auto_detect": True,
            "managers": sorted_managers,
            "disabled": disabled,
        }

    def save_config(self, config_data: Dict[str, Any]) -> None:
        """Saves configuration to disk with formatted YAML comments."""
        config_path = self.get_config_path()
        plat = config_data.get("platform", _get_current_platform_key())

        lines = [
            "# ==============================================================================",
            "#  💊 Kapsel Install Plugin - Cross-Platform Package Manager Priority Config",
            f"#  Auto-detected for platform: {plat}",
            "#  Managers listed under 'managers' execute in strict order from top to bottom.",
            "#  You can reorder, add, or move managers to 'disabled' at any time.",
            "# ==============================================================================",
            "",
            f'version: "{config_data.get("version", "1.0")}"',
            f'platform: "{plat}"',
            f'auto_detect: {str(config_data.get("auto_detect", True)).lower()}',
            "",
            "# Active package manager priority order (highest priority first):",
            "managers:",
        ]
        for m in config_data.get("managers", []):
            lines.append(f"  - {m}")

        lines.extend([
            "",
            "# Disabled package managers (ignored during install, update, and search):",
            "disabled:",
        ])
        for d in config_data.get("disabled", []):
            lines.append(f"  - {d}")
        lines.append("")

        with open(config_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        self._cached_config = config_data

    def get_active_managers(self) -> List[str]:
        """Returns the ordered list of enabled package managers."""
        conf = self.load_config()
        disabled = set(conf.get("disabled", []))
        return [m for m in conf.get("managers", []) if m not in disabled]

    def _inject_priority_args(self, args: List[str]) -> List[str]:
        """
        Injects '--<manager>' options in priority order into the argument list
        if the user did not pass any explicit manager selectors.
        """
        # Check if user already passed an explicit manager flag (e.g. '--winget', '--manager', '-m')
        explicit_flags = set(_load_defaults().get("mpm_explicit_flags", ["--manager", "-m", "--exclude", "-x"]))
        has_explicit = any(
            (arg.startswith("--") and arg[2:] in MANAGER_BINARIES)
            or arg in explicit_flags
            for arg in args
        )
        if has_explicit:
            return args

        active = self.get_active_managers()
        if not active:
            return args

        # Prepend ordered manager selection flags (e.g. ['--winget', '--scoop'])
        ordered_flags = [f"--{m}" for m in active]
        return ordered_flags + args

    # --------------------------------------------------------------------------
    # Command Handlers
    # --------------------------------------------------------------------------

    def handle_install(self, args: List[str], console: Optional[Console] = None) -> int:
        """Handles 'kps install' with subcommands: --order, --detect, --config."""
        con = console or Console(legacy_windows=False)

        # 1. Management Subcommands
        if any(arg in ("--order", "order") for arg in args):
            return self._show_order(con)
        if any(arg in ("--detect", "detect", "--rescan") for arg in args):
            return self._rescan_managers(con)
        if any(arg in ("--config", "config") for arg in args):
            con.print(f"[bold #00f0ff]Configuration File:[/] {self.get_config_path()}")
            con.print("[dim]You can edit this YAML file to customize manager priority order.[/]")
            return 0
        if any(arg in ("--help", "-h") for arg in args) and len(args) == 1:
            return self._show_install_help(con)

        # 2. Package Installation
        if not args:
            con.print("[bold #f43f5e]Error:[/] Please specify package name(s) to install.")
            con.print("[dim]Usage: kps install <package_name> [options][/]")
            con.print("[dim]       kps install --order   (view manager priority)[/]")
            con.print("[dim]       kps install --detect  (rescan system managers)[/]\n")
            return 1

        forwarded_args = self._inject_priority_args(args)
        return _run_mpm_command("install", forwarded_args, con)

    def handle_update(self, args: List[str], console: Optional[Console] = None) -> int:
        """Handles 'kps update' with priority injection."""
        con = console or Console(legacy_windows=False)
        forwarded_args = self._inject_priority_args(args)
        return _run_mpm_command("upgrade", forwarded_args, con)

    def handle_search(self, args: List[str], console: Optional[Console] = None) -> int:
        """Handles 'kps search' with priority injection."""
        con = console or Console(legacy_windows=False)
        if not args:
            con.print("[bold #f43f5e]Error:[/] Please specify a search query.")
            con.print("[dim]Usage: kps search <query>[/]\n")
            return 1
        forwarded_args = self._inject_priority_args(args)
        return _run_mpm_command("search", forwarded_args, con)

    def handle_sync(self, args: List[str], console: Optional[Console] = None) -> int:
        """
        Handles 'kps sync'.
        Requires '-mpm' or '--mpm' flag to trigger MPM sync.
        """
        con = console or Console(legacy_windows=False)
        has_mpm_flag = any(arg in ("-mpm", "--mpm") for arg in args)

        if has_mpm_flag:
            forwarded_args = [arg for arg in args if arg not in ("-mpm", "--mpm")]
            injected = self._inject_priority_args(forwarded_args)
            return _run_mpm_command("sync", injected, con)

        con.print("[bold #f59e0b]Notice:[/] General cloud synchronization is reserved for future releases.")
        con.print("To synchronize package manager configurations via MPM, please add the [bold #00f0ff]-mpm[/] flag:")
        con.print("    [bold #00f0ff]kps sync -mpm[/] [dim][options][/]\n")
        return 0

    # --------------------------------------------------------------------------
    # Interactive Inspection & Management UI
    # --------------------------------------------------------------------------

    def _show_order(self, con: Console) -> int:
        """Renders an elegant Rich Table showing package manager priority order."""
        conf = self.load_config()
        plat = conf.get("platform", _get_current_platform_key())
        managers = conf.get("managers", [])
        disabled = set(conf.get("disabled", []))
        cfg_path = self.get_config_path()

        table = Table(
            title="📦 Package Manager Priority Order",
            header_style="bold #00f0ff",
            border_style="#334155",
            expand=False,
        )
        table.add_column("Priority", justify="center", style="bold #a855f7", width=10)
        table.add_column("Manager ID", style="bold white", width=16)
        table.add_column("Status", justify="center", width=12)
        table.add_column("Executable Detected", style="dim", width=22)

        priority_idx = 1
        for m in managers:
            bins = MANAGER_BINARIES.get(m, (m,))
            found_bin = next((shutil.which(b) for b in bins if shutil.which(b)), None)

            if m in disabled:
                status_str = "[dim #6b7280]Disabled[/]"
                p_str = "[dim]-[/]"
            else:
                status_str = "[bold #10b981]Active[/]"
                p_str = f"#{priority_idx}"
                priority_idx += 1

            bin_str = f"[#10b981]✔[/] {Path(found_bin).name}" if found_bin else "[dim #f43f5e]✘ not in PATH[/]"
            table.add_row(p_str, m, status_str, bin_str)

        con.print()
        con.print(table)
        con.print(f"[dim]Platform:[/] [bold white]{plat}[/]  |  [dim]Config file:[/] [cyan]{cfg_path}[/]")
        con.print("[dim]Tip: Edit the config file or run 'kps install --detect' to refresh.[/]\n")
        return 0

    def _rescan_managers(self, con: Console) -> int:
        """Rescans the system, updates the configuration, and displays the result."""
        con.print("[bold #00f0ff]🔍 Rescanning system package managers...[/]")
        new_conf = self.generate_default_config()
        self.save_config(new_conf)
        con.print("[bold #10b981]✔ Package manager configuration updated successfully![/]")
        return self._show_order(con)

    def _show_install_help(self, con: Console) -> int:
        """Displays help for kps install."""
        con.print(
            Panel(
                "[bold white]Kapsel Unified Cross-Platform Installer[/]\n"
                "[dim]Powered by meta-package-manager (mpm) with intelligent priority scheduling.[/]\n\n"
                "[bold #00f0ff]Usage:[/]\n"
                "  kps install <package_name> [options]\n\n"
                "[bold #00f0ff]Priority & Configuration Commands:[/]\n"
                "  kps install --order       Show current package manager priority order\n"
                "  kps install --detect      Rescan installed package managers & update order\n"
                "  kps install --config      Display path to configuration file\n\n"
                "[bold #00f0ff]Direct MPM Passthrough Examples:[/]\n"
                "  kps install curl                   (installs with highest priority manager)\n"
                "  kps install --scoop neovim         (forces installation via Scoop)\n"
                "  kps install --dry-run ripgrep      (simulates install without making changes)",
                title="[bold #a855f7]kps install[/]",
                border_style="#00f0ff",
            )
        )
        return 0
