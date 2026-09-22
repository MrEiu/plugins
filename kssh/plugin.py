"""
Kapsel kssh Plugin - Main Plugin Entry & Command Dispatcher.
Registers 'kssh' command, auto-detects host targets, provides autocompletions,
and routes to the interactive picker or active SSH session bridge.
All comments and docstrings are in English.
"""

import argparse
import os
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from kapsel.ui.banner import ensure_utf8_io
from kapsel.core.plugin.base import KapselPlugin, PluginManifest
from kapsel.core.plugin.context import PluginContext
from kapsel.core.plugin.hooks import HookType

ensure_utf8_io()
from .config import find_host, load_hosts, remove_host
from .session import resolve_local_upload_path, run_ssh_session
from .transfer import execute_scp_upload
from .tui import render_host_picker
from .tunnel import tunnel_manager


def _parse_target_str(target: str) -> Tuple[str, str, int]:
    """
    Parses connection target string:
    - 'wsl'                  -> ('current', 'wsl', 22)
    - 'wsl:Ubuntu'           -> ('current', 'wsl:Ubuntu', 22)
    - 'root@124.12.15.4:2222' -> ('root', '124.12.15.4', 2222)
    - 'admin@192.168.1.10'    -> ('admin', '192.168.1.10', 22)
    - '10.0.0.8'              -> ('root', '10.0.0.8', 22)
    """
    user = "root"
    port = 22
    host = target.strip()

    if "@" in host:
        user_part, host = host.split("@", 1)
        if user_part:
            user = user_part

    # Handle WSL target aliases
    if host.lower() == "wsl" or host.lower().startswith("wsl:"):
        if user == "root":
            user = "current"
        return user, host, port

    if ":" in host:
        host_part, port_str = host.rsplit(":", 1)
        if port_str.isdigit():
            port = int(port_str)
            host = host_part

    return user, host, port


class KsshPlugin(KapselPlugin):
    """
    Kssh Plugin for Kapsel.
    Provides portable SSH host history, in-session Alt+S hotkey menu,
    file uploads targeting remote PWD with collision checking,
    bidirectional port forwarding, and seamless signal passthrough.
    """

    manifest = PluginManifest(
        id="kssh",
        name="Kssh",
        version="0.1.4",
        description="Ergonomic SSH & WSL companion with portable host history, in-session hotkeys, and transparent signal passthrough.",
        author="Kapsel Team",
        homepage="https://github.com/MrEiu/plugins/tree/master/kssh",
        min_kapsel_version="0.1.0",
        tags=["ssh", "wsl", "remote", "network", "tunnel", "upload"],
    )

    def on_load(self, context: PluginContext) -> None:
        """Registers 'kssh' command and dynamic completion hooks."""
        context.register_kps_command(
            name="kssh",
            handler=self.handle_kssh,
            help_text="Ergonomic SSH companion with host history and in-session operations",
            subcommands={
                "ls": "List recently connected hosts (max 4)",
                "rm": "Remove host from history (by number or alias)",
                "up": "Quick file upload to remote target",
                "port": "Establish background port forwarding",
            },
            usage="kssh [target|1-4] [-p port] [-n name] [-i key]",
            scope="feature",
        )

        # Register command filter to intercept bare 'kssh' in kapsel shell mode
        context.register_hook(HookType.FILTER_COMMAND, self.filter_command)
        # Register completion hook
        context.register_hook(HookType.PROVIDE_COMPLETIONS, self.provide_completions)

    def filter_command(self, raw_input: str) -> Tuple[bool, str]:
        """
        Intercepts 'kssh' invocations inside Kapsel shell mode and routes them cleanly.
        """
        stripped = raw_input.strip()
        if stripped == "kssh" or stripped.startswith("kssh "):
            # Let kps dispatcher handle it as 'kps kssh ...'
            parts = stripped.split(maxsplit=1)
            rem = parts[1] if len(parts) > 1 else ""
            return True, f"kps kssh {rem}".strip()
        return False, raw_input

    def provide_completions(self, line: str, cursor_pos: int) -> List[Dict[str, str]]:
        """Provides dynamic completions for saved host aliases and numbers (1-4)."""
        completions: List[Dict[str, str]] = []
        if not ("kssh" in line or "kps kssh" in line):
            return completions

        hosts = load_hosts()
        for idx, h in enumerate(hosts, 1):
            name = h.get("name") or h.get("host", "")
            target = f"{h.get('user', 'root')}@{h.get('host')}:{h.get('port', 22)}"
            completions.append({
                "value": str(idx),
                "display": f"[{idx}] {name}",
                "description": f"Connect to {target}",
            })
            if h.get("name") and h["name"] != str(idx):
                completions.append({
                    "value": h["name"],
                    "display": h["name"],
                    "description": f"Host {target}",
                })

        return completions

    def handle_kssh(self, args: List[str], console: Optional[Console] = None) -> int:
        """
        Main handler for 'kssh' command:
        - 'kssh' (bare)               -> Interactive 4-host quick picker
        - 'kssh 1' / 'kssh dev'       -> Direct connection from history
        - 'kssh root@124.12.15.4'     -> Connect to target and record in history
        - 'kssh ls'                   -> List saved hosts
        - 'kssh rm <id>'              -> Remove host from history
        - 'kssh up <file>'            -> Upload file
        - 'kssh port <spec>'          -> Establish port tunnel
        """
        con = console or Console(legacy_windows=False)

        # 1. Bare invocation -> Quick Picker TUI
        if not args:
            selected = render_host_picker(con)
            if not selected:
                return 0
            return run_ssh_session(
                host=selected["host"],
                user=selected.get("user", "root"),
                port=selected.get("port", 22),
                name=selected.get("name"),
                key_path=selected.get("key_path"),
                console=con,
            )

        first = args[0]

        # Help
        if first in ("-h", "--help", "help"):
            self._render_help(con)
            return 0

        # Subcommand: ls / list
        if first in ("ls", "list"):
            self._render_list(con)
            return 0

        # Subcommand: rm / remove
        if first in ("rm", "remove", "del"):
            if len(args) < 2:
                con.print("[bold #f43f5e]用法:[/] kssh rm <序号 1-4 或 别名>")
                return 1
            ident = args[1]
            if remove_host(ident):
                con.print(f"[bold #10b981]✓ 已移除主机:[/] [white]{ident}[/]")
                return 0
            else:
                con.print(f"[bold #f43f5e]未找到指定主机:[/] [white]{ident}[/]")
                return 1

        # Subcommand: port
        if first in ("port", "tunnel"):
            if len(args) < 2:
                con.print("[bold #f43f5e]用法:[/] kssh port <端口规则> [目标主机]")
                con.print("[dim]示例: kssh port 3306 1  (将主机 1 的 3306 转发到本地 3306)[/dim]")
                con.print("[dim]      kssh port 'r 8000' dev  (将本地 8000 反向代理到 dev 的 8000)[/dim]")
                return 1
            port_spec = args[1]
            host_ident = args[2] if len(args) > 2 else "1"
            h = find_host(host_ident)
            if not h:
                con.print(f"[bold #f43f5e]未找到目标主机:[/] [white]{host_ident}[/]")
                return 1
            ok, msg = tunnel_manager.start_tunnel(
                spec_str=port_spec,
                host=h["host"],
                user=h.get("user", "root"),
                ssh_port=h.get("port", 22),
                key_path=h.get("key_path"),
            )
            if ok:
                con.print(f"[bold #10b981]✓[/] {msg}")
                return 0
            else:
                con.print(f"[bold #f43f5e]失败:[/] {msg}")
                return 1

        # Subcommand: up / upload
        if first in ("up", "upload"):
            if len(args) < 2:
                con.print("[bold #f43f5e]用法:[/] kssh up <本地文件> [远程目录] [-t 目标主机]")
                return 1
            local_file = resolve_local_upload_path(args[1])
            remote_dir = args[2] if len(args) > 2 and not args[2].startswith("-") else "~"
            h = find_host("1")
            if not h:
                con.print("[bold #f43f5e]暂无可用主机，请指定目标主机。[/]")
                return 1
            filename = os.path.basename(local_file)
            remote_dest = f"{remote_dir.rstrip('/')}/{filename}"
            con.print(f"[bold #00f0ff]正在上传:[/] {local_file} -> {remote_dest}...")
            ok, msg = execute_scp_upload(
                local_path=local_file,
                remote_dest=remote_dest,
                host=h["host"],
                user=h.get("user", "root"),
                port=h.get("port", 22),
                key_path=h.get("key_path"),
            )
            if ok:
                con.print(f"[bold #10b981]✓ 上传成功:[/] {remote_dest}")
                return 0
            else:
                con.print(f"[bold #f43f5e]上传失败:[/] {msg}")
                return 1

        # Check if first arg is an existing host from history (index 1-4 or name)
        existing_host = find_host(first)
        if existing_host and (first.isdigit() or not any(c in first for c in ("@", ".", ":"))):
            return run_ssh_session(
                host=existing_host["host"],
                user=existing_host.get("user", "root"),
                port=existing_host.get("port", 22),
                name=existing_host.get("name"),
                key_path=existing_host.get("key_path"),
                extra_ssh_args=args[1:],
                console=con,
            )

        # Parse flags for new host connection
        parser = argparse.ArgumentParser(prog="kssh", add_help=False)
        parser.add_argument("target")
        parser.add_argument("-p", "--port", type=int, default=None)
        parser.add_argument("-n", "--name", type=str, default=None)
        parser.add_argument("-i", "--identity", type=str, default=None)

        known, extra = parser.parse_known_args(args)
        parsed_user, parsed_host, parsed_port = _parse_target_str(known.target)

        final_port = known.port or parsed_port or 22
        final_user = parsed_user or "root"
        final_name = known.name or parsed_host

        return run_ssh_session(
            host=parsed_host,
            user=final_user,
            port=final_port,
            name=final_name,
            key_path=known.identity,
            extra_ssh_args=extra,
            console=con,
        )

    def _render_list(self, con: Console) -> None:
        """Renders saved host history table."""
        hosts = load_hosts()
        if not hosts:
            con.print("\n[dim]暂无已保存的 SSH 主机记录。[/]\n")
            return

        table = Table(
            show_header=True,
            header_style="bold #38bdf8",
            box=None,
            pad_edge=False,
        )
        table.add_column("序号", style="bold #00f0ff", width=6)
        table.add_column("别名 / 主机", style="bold white", width=18)
        table.add_column("连接目标", style="#a78bfa", width=30)
        table.add_column("最近连接时间", style="dim", width=20)

        for i, h in enumerate(hosts, 1):
            name = h.get("name") or h.get("host", "unknown")
            target = f"{h.get('user', 'root')}@{h.get('host')}:{h.get('port', 22)}"
            last_time = h.get("last_connected", "never")
            table.add_row(f" [{i}]", name, target, last_time)

        panel = Panel(
            table,
            title="[bold #00f0ff]🌐 Kssh 已保存主机 (最多 4 台)[/]",
            subtitle="[dim]直接运行 'kssh <序号>' 或 'kssh <别名>' 连接[/dim]",
            border_style="#0284c7",
        )
        con.print()
        con.print(panel)
        con.print()

    def _render_help(self, con: Console) -> None:
        """Renders comprehensive help dashboard."""
        con.print("\n[bold #00f0ff]🌐 Kssh - 便携式 SSH 伴侣[/]\n")
        con.print("[bold white]基本用法:[/]")
        con.print("  [bold #38bdf8]kssh[/]                         打开最近主机快捷选择器 (1-4 单键直连)")
        con.print("  [bold #38bdf8]kssh 1[/]                       直接连接历史中的第 1 台主机")
        con.print("  [bold #38bdf8]kssh dev[/]                     按别名连接已保存的主机")
        con.print("  [bold #38bdf8]kssh root@124.12.15.4[/]        连接新主机 (自动保存至历史，最多 4 台)")
        con.print("  [bold #38bdf8]kssh -n prod root@10.0.0.1 -p 3030[/]  连接并赋予别名与自定义端口\n")

        con.print("[bold white]会话内快捷操作 (连上服务器以后):[/]")
        con.print("  [bold #f59e0b]Alt+S[/]                       呼出底部操作菜单:")
        con.print("    [bold #38bdf8]u[/] : [white]上传文件到远程当前目录 (自动检测 PWD，存在同名文件提示覆盖/重命名)[/]")
        con.print("    [bold #38bdf8]p[/] : [white]建立端口转发 (直接输 3306 为远端->本地，输 r 8000 为本地->远端反向代理)[/]")
        con.print("    [bold #38bdf8]Esc[/] : [white]取消操作并立即恢复远程命令行[/]\n")

        con.print("[bold white]管理子命令:[/]")
        con.print("  [bold #38bdf8]kssh ls[/]                      查看当前已保存的主机清单")
        con.print("  [bold #38bdf8]kssh rm <1-4 或 别名>[/]        从历史中删除指定主机\n")
