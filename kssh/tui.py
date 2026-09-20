"""
Kapsel kssh Plugin - Interactive Host Picker TUI.
Displays a compact list of recently connected hosts (max 4).
Supports 1-keystroke connection (1-4), deletion (d), and exit (q).
All comments and docstrings are in English.
"""

import os
import sys
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from kapsel.ui.banner import ensure_utf8_io
from .config import load_hosts, remove_host

ensure_utf8_io()


def _read_single_key() -> str:
    """Reads a single keypress without waiting for Enter on Windows, with fallback."""
    if sys.platform == "win32":
        try:
            import msvcrt
            ch = msvcrt.getch()
            if ch in (b"\x00", b"\xe0"):
                # Extended key (arrow keys, function keys)
                ext = msvcrt.getch()
                return f"ext_{ord(ext)}"
            if ch == b"\x1b":
                return "esc"
            if ch == b"\r":
                return "enter"
            if ch == b"\x03":
                return "ctrl_c"
            return ch.decode("utf-8", errors="ignore")
        except Exception:
            pass

    # Standard fallback
    try:
        val = input()
        return val.strip()[:1] if val.strip() else "enter"
    except (KeyboardInterrupt, EOFError):
        return "ctrl_c"


def render_host_picker(console: Optional[Console] = None) -> Optional[Dict[str, Any]]:
    """
    Renders the interactive 4-host quick-connect picker.
    Returns the selected host dictionary, or None if user canceled.
    """
    con = console or Console(legacy_windows=False)

    while True:
        hosts = load_hosts()
        if not hosts:
            con.print("\n[bold #00f0ff]🌐 Kssh[/] - [dim]暂无保存的连接记录。[/]")
            con.print("[dim]直接连接主机即可自动保存 (最多保留最近 4 台):[/]")
            con.print("  [bold #38bdf8]kssh root@124.12.15.4[/]")
            con.print("  [bold #38bdf8]kssh root@192.168.1.100 -p 3030 -n dev[/]\n")
            return None

        table = Table(
            show_header=True,
            header_style="bold #38bdf8",
            box=None,
            pad_edge=False,
            collapse_padding=True,
        )
        table.add_column("序号", style="bold #00f0ff", width=6)
        table.add_column("别名 / 主机", style="bold white", width=18)
        table.add_column("连接目标", style="#a78bfa", width=32)
        table.add_column("最近连接", style="dim", width=20)

        for i, h in enumerate(hosts, 1):
            name = h.get("name") or h.get("host", "unknown")
            target = f"{h.get('user', 'root')}@{h.get('host')}:{h.get('port', 22)}"
            last_time = h.get("last_connected", "never")
            table.add_row(f" [{i}]", name, target, last_time)

        panel = Panel(
            table,
            title="[bold #00f0ff]🌐 Kssh 最近连接主机[/]",
            subtitle="[dim]按 [1-4] 快捷连接  |  [d] 删除  |  [q/Esc] 退出[/dim]",
            border_style="#0284c7",
        )
        con.print()
        con.print(panel)
        con.print("[bold #38bdf8]请选择 [1-{max_idx}] 或输入操作:[/] ".format(max_idx=len(hosts)), end="")

        key = _read_single_key()
        con.print(key if len(key) == 1 else "")

        if key in ("q", "Q", "esc", "ctrl_c"):
            con.print("[dim]已退出。[/]")
            return None

        # Number key 1-4
        if key.isdigit():
            idx = int(key) - 1
            if 0 <= idx < len(hosts):
                selected = hosts[idx]
                con.print(f"[bold #10b981]✓ 选择:[/] [white]{selected.get('name') or selected.get('host')}[/]")
                return selected
            else:
                con.print(f"[bold #f43f5e]无效的序号:[/] {key}")
                continue

        # Delete host
        if key in ("d", "D"):
            con.print("[bold #f59e0b]请输入要删除的序号 [1-{max_idx}] (回车取消): [/]".format(max_idx=len(hosts)), end="")
            del_key = _read_single_key()
            con.print(del_key if len(del_key) == 1 else "")
            if del_key.isdigit():
                d_idx = int(del_key) - 1
                if 0 <= d_idx < len(hosts):
                    target = hosts[d_idx]
                    remove_host(str(d_idx + 1))
                    con.print(f"[dim]已移除:[/] {target.get('name') or target.get('host')}")
            continue

        con.print("[dim]提示: 请按数字 1-{max_idx} 或 q 退出。[/]".format(max_idx=len(hosts)))
