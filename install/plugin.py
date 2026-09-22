"""
Install Plugin for Kapsel.
Bridges meta-package-manager (mpm) to provide unified cross-platform package operations.
Features intelligent package manager auto-detection, platform-adaptive priority ordering,
and an independent persistent configuration file.
All comments and descriptions are in English.
"""

import os
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

try:
    from .streaming_search import concurrent_streaming_search, SearchItem
    from .interactive import select_package_interactive, search_and_select_interactive
    from .inspector import inspect_installed_package
    from .batch import install_packages_batch
except ImportError:
    from plugins.install.streaming_search import concurrent_streaming_search, SearchItem
    from plugins.install.interactive import select_package_interactive, search_and_select_interactive
    from plugins.install.inspector import inspect_installed_package
    from plugins.install.batch import install_packages_batch

try:
    from kapsel.core.tools.registry import get_tool
    from kapsel.core.tools.installer import install_tool
except ImportError:
    get_tool = None
    install_tool = None



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

# Set of manager IDs known not to be supported as CLI flags by MPM
UNSUPPORTED_MPM_SELECTORS: set = {"go", "dotnet"}
MPM_SUPPORTED_SELECTORS: set = set(MANAGER_BINARIES.keys()) - UNSUPPORTED_MPM_SELECTORS


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
    Locates the meta-package-manager (mpm) or kapsel-mpm CLI executable.
    Prioritizes customized 'kapsel-mpm', then local Kapsel bin directory, then system mpm.
    """
    # 1. kapsel-mpm in System PATH
    kmpm_path = shutil.which("kapsel-mpm") or shutil.which("kmpm")
    if kmpm_path:
        return [kmpm_path]

    # 2. Local Kapsel bin directory (~/.kapsel/bin/kapsel-mpm)
    local_kmpm = get_kapsel_dir() / "bin" / ("kapsel-mpm.exe" if sys.platform == "win32" else "kapsel-mpm")
    if local_kmpm.exists():
        return [str(local_kmpm)]

    # 3. Standard mpm in System PATH
    mpm_path = shutil.which("mpm")
    if mpm_path:
        return [mpm_path]

    # 4. Local Kapsel bin directory (~/.kapsel/bin/mpm)
    local_bin = get_kapsel_dir() / "bin" / ("mpm.exe" if sys.platform == "win32" else "mpm")
    if local_bin.exists():
        return [str(local_bin)]

    # 5. Python environment module (pip)
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


def _run_mpm_command(
    subcmd: str,
    args: List[str],
    console: Optional[Console] = None,
    custom_paths: Optional[Dict[str, str]] = None,
) -> int:
    """
    Executes an MPM or kapsel-mpm subcommand with forwarded arguments.
    Prompts the user with installation methods if neither is found.
    Injects custom package manager paths and environment variables into the execution context.
    """
    con = console or Console(legacy_windows=False)
    mpm_exec = _resolve_mpm_executable()

    if not mpm_exec:
        con.print("[bold #f43f5e]Error:[/] [white]Neither kapsel-mpm nor meta-package-manager (mpm) is installed.[/]")
        con.print("[dim]Install kapsel-mpm or mpm via one of the following methods:[/]")
        con.print("    [bold #00f0ff]pip install kapsel-mpm[/]  (Recommended: tailored for Kapsel)")
        if sys.platform == "win32":
            con.print("    [bold #00f0ff]scoop install main/meta-package-manager[/]  (Scoop)")
        else:
            con.print("    [bold #00f0ff]brew install meta-package-manager[/]  (Homebrew)")
        con.print("    [bold #a855f7]pip install meta-package-manager[/]  (Python pip)\n")
        return 1

    # MPM requires manager selector options (--<manager>, --no-<manager>) before the subcommand
    global_flags: List[str] = []
    subcmd_args: List[str] = []
    for a in args:
        if (a.startswith("--") and (a[2:] in MANAGER_BINARIES or a.startswith("--no-"))) or a in ("--dry-run",):
            global_flags.append(a)
        else:
            subcmd_args.append(a)

    cmd = mpm_exec + global_flags + [subcmd] + subcmd_args
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    # Prepend custom manager executable directories to PATH and set KAPSEL_MPM_<ID>_PATH
    if custom_paths:
        dirs_to_add: List[str] = []
        for mid, p in custom_paths.items():
            p_path = Path(p)
            d = str(p_path.parent if p_path.is_file() else p_path)
            if d not in dirs_to_add and os.path.isdir(d):
                dirs_to_add.append(d)
            # Inject direct path variable for kapsel-mpm engine
            env[f"KAPSEL_MPM_{mid.upper().replace('-', '_')}_PATH"] = str(p_path)
        if dirs_to_add:
            env["PATH"] = os.pathsep.join(dirs_to_add) + os.pathsep + env.get("PATH", "")

    try:
        # Stream process execution interactively to the terminal
        result = subprocess.run(cmd, env=env)
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
        version="0.2.8",
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
            usage="kps install <package_name...> [options]",
            subcommands={
                "add": "Add package manager to active priority list: kps install add <mgr>",
                "rm": "Remove / disable package manager: kps install rm <mgr>",
                "order": "View or customize package manager priority order: kps install order [m1 m2...]",
                "up": "Move package manager up in priority: kps install up <mgr>",
                "down": "Move package manager down in priority: kps install down <mgr>",
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
                        if "custom_paths" not in data or not isinstance(data["custom_paths"], dict):
                            data["custom_paths"] = {}
                        for mid, cp in data["custom_paths"].items():
                            MANAGER_BINARIES[mid] = (Path(cp).name, mid)
                            MPM_SUPPORTED_SELECTORS.add(mid)
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
            "custom_paths": {},
            "managers": sorted_managers,
            "disabled": disabled,
        }

    def save_config(self, config_data: Dict[str, Any]) -> None:
        """Saves configuration to disk with formatted YAML comments."""
        config_path = self.get_config_path()
        plat = config_data.get("platform", _get_current_platform_key())
        custom_paths = config_data.get("custom_paths", {})

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
            "# Custom executable paths for package managers (e.g. scoop: C:\\Users\\...\\scoop.cmd):",
            "custom_paths:",
        ]
        if custom_paths:
            for k, v in custom_paths.items():
                escaped_v = yaml.safe_dump(str(v)).strip()
                lines.append(f"  {k}: {escaped_v}")
        else:
            lines.append("  {}")

        lines.extend([
            "",
            "# Active package manager priority order (highest priority first):",
            "managers:",
        ])
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
        # Only inject flags for managers actually supported as CLI selectors by MPM
        ordered_flags = [f"--{m}" for m in active if m in MPM_SUPPORTED_SELECTORS]
        return ordered_flags + args

    # --------------------------------------------------------------------------
    # Command Handlers
    # --------------------------------------------------------------------------

    def handle_install(self, args: List[str], console: Optional[Console] = None) -> int:
        """Handles 'kps install' with subcommands: add, rm, order, up, down, --detect, --config, and package installations."""
        con = console or Console(legacy_windows=False)

        if not args:
            return self._show_install_help(con)

        first_arg = args[0].lower()

        # 1. Management Subcommands
        if first_arg in ("--help", "-h"):
            return self._show_install_help(con)
        if first_arg == "add":
            return self._handle_add_manager(args[1:], con)
        if first_arg in ("rm", "remove", "del", "delete", "disable"):
            return self._handle_remove_manager(args[1:], con)
        if first_arg in ("order", "sort"):
            return self._handle_order_manager(args[1:], con)
        if first_arg == "up":
            return self._handle_move_manager(args[1:], direction=-1, con=con)
        if first_arg == "down":
            return self._handle_move_manager(args[1:], direction=1, con=con)
        if first_arg in ("--detect", "detect", "--rescan", "rescan"):
            return self._rescan_managers(con)
        if first_arg in ("--config", "config"):
            con.print(f"[bold #00f0ff]Configuration File:[/] {self.get_config_path()}")
            con.print("[dim]You can edit this YAML file to customize manager priority order.[/]")
            return 0

        # Also support legacy flag variants anywhere in args (e.g. kps install --order)
        if any(arg in ("--order",) for arg in args):
            return self._show_order(con)
        if any(arg in ("--detect", "--rescan") for arg in args):
            return self._rescan_managers(con)
        if any(arg in ("--config",) for arg in args):
            con.print(f"[bold #00f0ff]Configuration File:[/] {self.get_config_path()}")
            return 0

        conf = self.load_config()
        custom_paths = conf.get("custom_paths", {})

        # 2. Package Installation
        pkg_names = [a for a in args if not a.startswith("-")]
        if not pkg_names:
            con.print("[bold #f43f5e]Error:[/] Please specify package name(s) to install.")
            con.print("[dim]Usage: kps install <package_name...> [options][/]")
            con.print("[dim]       kps install add <mgr> [path]  (add package manager)[/]")
            con.print("[dim]       kps install rm <mgr>          (disable package manager)[/]")
            con.print("[dim]       kps install order [m1 m2...]  (view or customize priority)[/]\n")
            return 1

        # Multi-package workflow (len(pkg_names) > 1):
        # Automatically routes to MultiPackageInstaller for concurrent/parallel delivery!
        if len(pkg_names) > 1:
            return install_packages_batch(
                packages=pkg_names,
                args=args,
                plugin=self,
                console=con,
            )

        pkg_name = pkg_names[0]

        # 2a. Check if tool is declared in Kapsel declarative tool registry (tools.yaml)
        if pkg_name and get_tool and not any(a.startswith("--") for a in args):
            tool_def = get_tool(pkg_name)
            if tool_def:
                con.print(f"[bold #00f0ff]🎯 Found '{pkg_name}' in Kapsel declarative tool registry.[/]")
                con.print(f"[dim]Executing deterministic delivery strategy (origin: {tool_def.get('plugin', 'core')})...[/]")
                ok = install_tool(pkg_name, console=con)
                if ok:
                    inspect_installed_package(pkg_name, manager="declarative (tools.yaml)", console=con)
                    return 0
                else:
                    con.print(f"[yellow]Declarative installation failed. Falling back to package managers...[/]")

        # 2b. Stranger package workflow: if no explicit manager or -y/--yes/--direct flag,
        # in interactive TTY, first execute concurrent streaming search with dynamic display,
        # prompt with secondary interactive confirmation, install selected package, and inspect.
        is_direct = any(a in ("-y", "--yes", "--direct", "--blind") for a in args)
        has_explicit_manager = any(
            (a.startswith("--") and a[2:] in MANAGER_BINARIES)
            or a in ("--manager", "-m")
            for a in args
        )
        is_search_flag = any(a in ("-s", "--search", "-i", "--interactive") for a in args)

        if pkg_name and (is_search_flag or (sys.stdin.isatty() and not is_direct and not has_explicit_manager)):
            mpm_exec = _resolve_mpm_executable()
            if mpm_exec:
                active_managers = self.get_active_managers()
                selected = search_and_select_interactive(
                    mpm_exec=mpm_exec,
                    managers=active_managers,
                    query=pkg_name,
                    console=con,
                )
                if selected:
                    con.print(f"\n[bold #38bdf8]⚡ Installing [white]{selected.package_id}[/] via [cyan]{selected.manager}[/]...[/]\n")
                    install_args = [f"--{selected.manager}", selected.package_id]
                    ret = _run_mpm_command("install", install_args, con, custom_paths=custom_paths)
                    if ret == 0:
                        inspect_installed_package(selected.package_id, manager=selected.manager, console=con)
                    return ret
                else:
                    con.print("[dim]Installation cancelled by user.[/]")
                    return 0

        forwarded_args = self._inject_priority_args(args)
        ret = _run_mpm_command("install", forwarded_args, con, custom_paths=custom_paths)
        if ret == 0 and pkg_name and not any(a in ("--dry-run", "-h", "--help") for a in args):
            detected_mgr = "mpm"
            for a in forwarded_args:
                if a.startswith("--") and a[2:] in MANAGER_BINARIES:
                    detected_mgr = a[2:]
                    break
            inspect_installed_package(pkg_name, manager=detected_mgr, console=con)
        return ret

    def handle_update(self, args: List[str], console: Optional[Console] = None) -> int:
        """Handles 'kps update' with priority injection."""
        con = console or Console(legacy_windows=False)
        conf = self.load_config()
        custom_paths = conf.get("custom_paths", {})
        forwarded_args = self._inject_priority_args(args)
        return _run_mpm_command("upgrade", forwarded_args, con, custom_paths=custom_paths)

    def handle_search(self, args: List[str], console: Optional[Console] = None) -> int:
        """
        Handles 'kps search' with concurrent multi-manager streaming search
        and optional secondary interactive confirmation.
        """
        con = console or Console(legacy_windows=False)
        conf = self.load_config()
        custom_paths = conf.get("custom_paths", {})

        if not args:
            con.print("[bold #f43f5e]Error:[/] Please specify a search query.")
            con.print("[dim]Usage: kps search <query> [options][/]\n")
            return 1

        # Fallback to direct mpm search if raw/plain/columns flags specified
        if any(a in ("--raw", "--plain", "--columns") for a in args):
            forwarded_args = [a for a in args if a not in ("--raw", "--plain")]
            forwarded_args = self._inject_priority_args(forwarded_args)
            return _run_mpm_command("search", forwarded_args, con, custom_paths=custom_paths)

        mpm_exec = _resolve_mpm_executable()
        if not mpm_exec:
            con.print("[bold #f43f5e]Error:[/] meta-package-manager (mpm) is not installed.")
            return 1

        query = " ".join([a for a in args if not a.startswith("-")])
        if not query:
            return _run_mpm_command("search", args, con, custom_paths=custom_paths)

        active_managers = self.get_active_managers()

        # Interactive progressive selection if connected to interactive terminal
        if sys.stdin.isatty():
            selected = search_and_select_interactive(
                mpm_exec=mpm_exec,
                managers=active_managers,
                query=query,
                console=con,
            )
            if selected:
                con.print(f"\n[bold #38bdf8]⚡ Installing [white]{selected.package_id}[/] via [cyan]{selected.manager}[/]...[/]\n")
                install_args = [f"--{selected.manager}", selected.package_id]
                ret = _run_mpm_command("install", install_args, con, custom_paths=custom_paths)
                if ret == 0:
                    inspect_installed_package(selected.package_id, manager=selected.manager, console=con)
                return ret
            return 0

        # Non-interactive / headless fallback
        results = concurrent_streaming_search(
            mpm_exec=mpm_exec,
            managers=active_managers,
            query=query,
            console=con,
        )
        return 0

    def handle_sync(self, args: List[str], console: Optional[Console] = None) -> int:
        """
        Handles 'kps sync'.
        Requires '-mpm' or '--mpm' flag to trigger MPM sync.
        """
        con = console or Console(legacy_windows=False)
        has_mpm_flag = any(arg in ("-mpm", "--mpm") for arg in args)

        if has_mpm_flag:
            conf = self.load_config()
            custom_paths = conf.get("custom_paths", {})
            forwarded_args = [arg for arg in args if arg not in ("-mpm", "--mpm")]
            injected = self._inject_priority_args(forwarded_args)
            return _run_mpm_command("sync", injected, con, custom_paths=custom_paths)

        con.print("[bold #f59e0b]Notice:[/] General cloud synchronization is reserved for future releases.")
        con.print("To synchronize package manager configurations via MPM, please add the [bold #00f0ff]-mpm[/] flag:")
        con.print("    [bold #00f0ff]kps sync -mpm[/] [dim][options][/]\n")
        return 0

    # --------------------------------------------------------------------------
    # Package Manager Management Handlers
    # --------------------------------------------------------------------------

    def _handle_add_manager(self, args: List[str], con: Console) -> int:
        """
        Adds or enables a package manager in the active priority list.
        Supports specifying an explicit executable location.
        Usage:
            kps install add <mgr> [path]
            kps install add <mgr> --path <path>
            kps install add <path_to_binary>
        """
        if not args:
            con.print("[bold #f43f5e]Error:[/] Missing package manager identifier or path.")
            con.print("[bold #00f0ff]Usage:[/]")
            con.print("  kps install add <mgr> <path_to_executable>  (add manager with custom path)")
            con.print("  kps install add <path_to_executable>       (auto-infer manager ID from file)")
            con.print("  kps install add <mgr>                      (enable manager detected in system PATH)")
            con.print("[dim]Examples:[/]")
            con.print("  kps install add scoop C:\\Users\\user\\scoop\\shims\\scoop.cmd")
            con.print("  kps install add winget")
            return 1

        mgr_name: Optional[str] = None
        custom_path_str: Optional[str] = None

        # Parse flags vs positional
        i = 0
        positional: List[str] = []
        while i < len(args):
            arg = args[i]
            if arg in ("--path", "-p") and i + 1 < len(args):
                custom_path_str = args[i + 1]
                i += 2
            elif arg.startswith("--path="):
                custom_path_str = arg.split("=", 1)[1]
                i += 1
            else:
                positional.append(arg)
                i += 1

        if not custom_path_str and len(positional) >= 2:
            mgr_name = positional[0].lower().strip()
            custom_path_str = positional[1]
        elif positional:
            first = positional[0].strip()
            # If the single positional argument looks like a file path
            p_obj = Path(first)
            if ("/" in first or "\\" in first or p_obj.exists() or p_obj.suffix in (".exe", ".cmd", ".bat", ".sh", ".ps1")):
                custom_path_str = first
                mgr_name = p_obj.stem.lower()
            else:
                mgr_name = first.lower()

        if not mgr_name and not custom_path_str:
            con.print("[bold #f43f5e]Error:[/] Could not determine package manager name or path.")
            return 1

        resolved_path: Optional[Path] = None

        if custom_path_str:
            clean_str = custom_path_str.strip("\"'")
            expanded = os.path.expandvars(os.path.expanduser(clean_str))
            target_path = Path(expanded).resolve()

            if not target_path.exists():
                con.print(f"[bold #f43f5e]Error:[/] Specified path does not exist: [white]{clean_str}[/]")
                return 1

            if target_path.is_dir():
                candidate_names = [mgr_name] if mgr_name else []
                candidate_names.extend([
                    f"{mgr_name}.exe", f"{mgr_name}.cmd", f"{mgr_name}.bat", f"{mgr_name}.ps1",
                ])
                found = next((target_path / c for c in candidate_names if (target_path / c).is_file()), None)
                if found:
                    resolved_path = found
                else:
                    con.print(f"[bold #f43f5e]Error:[/] Provided path is a directory and no '{mgr_name}' executable was found inside: [white]{target_path}[/]")
                    return 1
            else:
                resolved_path = target_path

            if not mgr_name:
                mgr_name = resolved_path.stem.lower()

        # If no custom path was provided, check if the manager is found in system PATH
        if not resolved_path:
            bins = MANAGER_BINARIES.get(mgr_name, (mgr_name,))
            found_bin = next((shutil.which(b) for b in bins if shutil.which(b)), None)
            if not found_bin:
                con.print(f"[bold #f43f5e]Error:[/] Package manager '[cyan]{mgr_name}[/]' is not found in system PATH.")
                con.print("[dim]Please specify the location of the package manager executable:[/]")
                con.print(f"    [bold #00f0ff]kps install add {mgr_name} <path_to_executable>[/]\n")
                return 1
            else:
                resolved_path = Path(found_bin)

        # Update configuration
        conf = self.load_config()
        managers = conf.setdefault("managers", [])
        disabled = conf.setdefault("disabled", [])
        custom_paths = conf.setdefault("custom_paths", {})

        if custom_path_str or resolved_path:
            custom_paths[mgr_name] = str(resolved_path)

        # Register in runtime registries
        MANAGER_BINARIES[mgr_name] = (resolved_path.name, mgr_name)
        MPM_SUPPORTED_SELECTORS.add(mgr_name)

        if mgr_name in disabled:
            disabled.remove(mgr_name)

        if mgr_name not in managers:
            managers.append(mgr_name)

        self.save_config(conf)

        con.print(f"[bold #10b981]✔ Successfully added package manager '[cyan]{mgr_name}[/]'![/]")
        con.print(f"  [dim]Executable path:[/] [white]{resolved_path}[/]")
        return self._show_order(con)

    def _handle_remove_manager(self, args: List[str], con: Console) -> int:
        """Removes or disables a package manager."""
        if not args:
            con.print("[bold #f43f5e]Error:[/] Please specify the manager ID to remove/disable.")
            con.print("[dim]Usage: kps install rm <manager>[/]")
            con.print("[dim]Example: kps install rm pip[/]")
            return 1

        mgr = args[0].lower().strip()
        conf = self.load_config()
        managers = conf.get("managers", [])
        disabled = conf.setdefault("disabled", [])

        if mgr not in managers and mgr not in disabled:
            con.print(f"[bold #f43f5e]Error:[/] Package manager '[cyan]{mgr}[/]' is not configured.")
            return 1

        if mgr in managers:
            managers.remove(mgr)
        if mgr not in disabled:
            disabled.append(mgr)

        self.save_config(conf)
        con.print(f"[bold #10b981]✔ Successfully disabled package manager '[cyan]{mgr}[/]'.[/]")
        con.print("[dim]It will no longer be used for install, update, or search operations.[/]")
        return self._show_order(con)

    def _handle_order_manager(self, args: List[str], con: Console) -> int:
        """Displays or sets explicit package manager priority order."""
        if not args:
            return self._show_order(con)

        new_order = [a.lower().strip() for a in args if not a.startswith("-")]
        if not new_order:
            return self._show_order(con)

        conf = self.load_config()
        current_managers = conf.get("managers", [])
        disabled = set(conf.get("disabled", []))

        final_managers: List[str] = []
        for m in new_order:
            if m in disabled:
                disabled.remove(m)
            if m not in final_managers:
                final_managers.append(m)

        for m in current_managers:
            if m not in final_managers and m not in disabled:
                final_managers.append(m)

        conf["managers"] = final_managers
        conf["disabled"] = list(disabled)
        self.save_config(conf)
        con.print("[bold #10b981]✔ Package manager priority order updated successfully![/]")
        return self._show_order(con)

    def _handle_move_manager(self, args: List[str], direction: int, con: Console) -> int:
        """Moves a package manager up or down in priority order."""
        action_name = "up" if direction < 0 else "down"
        if not args:
            con.print(f"[bold #f43f5e]Error:[/] Please specify the manager ID to move {action_name}.")
            con.print(f"[dim]Usage: kps install {action_name} <manager>[/]")
            return 1

        mgr = args[0].lower().strip()
        conf = self.load_config()
        managers = conf.get("managers", [])

        if mgr not in managers:
            if mgr in conf.get("disabled", []):
                con.print(f"[bold #f59e0b]Notice:[/] Manager '[cyan]{mgr}[/]' is currently disabled.")
                con.print(f"Enable it first via: [bold #00f0ff]kps install add {mgr}[/]")
            else:
                con.print(f"[bold #f43f5e]Error:[/] Manager '[cyan]{mgr}[/]' is not in the active manager list.")
            return 1

        idx = managers.index(mgr)
        new_idx = idx + direction

        if new_idx < 0:
            con.print(f"[bold #f59e0b]Notice:[/] '[cyan]{mgr}[/]' is already at the highest priority.")
            return 0
        if new_idx >= len(managers):
            con.print(f"[bold #f59e0b]Notice:[/] '[cyan]{mgr}[/]' is already at the lowest priority.")
            return 0

        managers[idx], managers[new_idx] = managers[new_idx], managers[idx]
        conf["managers"] = managers
        self.save_config(conf)
        con.print(f"[bold #10b981]✔ Moved '[cyan]{mgr}[/]' {action_name} in priority.[/]")
        return self._show_order(con)

    # --------------------------------------------------------------------------
    # Interactive Inspection & Management UI
    # --------------------------------------------------------------------------

    def _show_order(self, con: Console) -> int:
        """Renders an elegant Rich Table showing package manager priority order."""
        conf = self.load_config()
        plat = conf.get("platform", _get_current_platform_key())
        managers = conf.get("managers", [])
        disabled = conf.get("disabled", [])
        custom_paths = conf.get("custom_paths", {})
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
        table.add_column("Executable Path / Status", style="dim", width=36)

        priority_idx = 1
        for m in managers:
            status_str = "[bold #10b981]Active[/]"
            p_str = f"#{priority_idx}"
            priority_idx += 1

            if m in custom_paths:
                cp = Path(custom_paths[m])
                if cp.exists():
                    bin_str = f"[#10b981]✔ (custom)[/] {cp.name} [dim]({cp.parent})[/]"
                else:
                    bin_str = f"[#f43f5e]✘ missing:[/] [dim]{cp}[/]"
            else:
                bins = MANAGER_BINARIES.get(m, (m,))
                found_bin = next((shutil.which(b) for b in bins if shutil.which(b)), None)
                bin_str = f"[#10b981]✔[/] {Path(found_bin).name}" if found_bin else "[dim #f43f5e]✘ not in PATH[/]"

            table.add_row(p_str, m, status_str, bin_str)

        for m in disabled:
            status_str = "[dim #6b7280]Disabled[/]"
            p_str = "[dim]-[/]"
            if m in custom_paths:
                cp = Path(custom_paths[m])
                bin_str = f"[dim](custom) {cp.name}[/]"
            else:
                bins = MANAGER_BINARIES.get(m, (m,))
                found_bin = next((shutil.which(b) for b in bins if shutil.which(b)), None)
                bin_str = f"[dim]{Path(found_bin).name}[/]" if found_bin else "[dim]not in PATH[/]"
            table.add_row(p_str, m, status_str, bin_str)

        con.print()
        con.print(table)
        con.print(f"[dim]Platform:[/] [bold white]{plat}[/]  |  [dim]Config file:[/] [cyan]{cfg_path}[/]")
        con.print("[dim]Commands: 'kps install add <mgr> [path]', 'rm <mgr>', 'order [m1 m2...]', 'up <mgr>', 'down <mgr>'[/]\n")
        return 0

    def _rescan_managers(self, con: Console) -> int:
        """Rescans the system, updates the configuration, and displays the result."""
        con.print("[bold #00f0ff]🔍 Rescanning system package managers...[/]")
        old_conf = self.load_config()
        old_custom = old_conf.get("custom_paths", {})
        new_conf = self.generate_default_config()
        # Preserve user custom paths across rescans
        new_conf["custom_paths"] = old_custom
        for mid in old_custom:
            if mid not in new_conf["managers"]:
                new_conf["managers"].append(mid)
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
                "  kps install <package_name...> [options]\n\n"
                "[bold #00f0ff]Package Manager Management Commands:[/]\n"
                "  kps install add <mgr> [path]   Add manager to active list (optionally pass executable path)\n"
                "  kps install rm <mgr>           Disable/remove manager from active priority\n"
                "  kps install order [m1 m2...]   View or set explicit priority order\n"
                "  kps install up <mgr>           Increase manager priority\n"
                "  kps install down <mgr>         Decrease manager priority\n"
                "  kps install --detect           Rescan system package managers\n"
                "  kps install --config           Show configuration file path\n\n"
                "[bold #00f0ff]Installation Examples:[/]\n"
                "  kps install curl git           (batch installs multiple packages concurrently)\n"
                "  kps install --scoop neovim     (forces installation via Scoop)\n"
                "  kps install --dry-run ripgrep  (simulates install without making changes)",
                title="[bold #a855f7]kps install[/]",
                border_style="#00f0ff",
            )
        )
        return 0
