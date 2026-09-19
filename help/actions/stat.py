"""
HTTP Stat and Latency Waterfall Analyzer for Help Plugin.
Measures and visualizes HTTP timing phases (DNS, TCP, TLS, TTFB, Transfer).
All comments and docstrings are in English.
"""

from pathlib import Path
import shutil
import socket
import ssl
import subprocess
import sys
import time
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

try:
    from ..ui import select_interactive_item
except ImportError:
    from plugins.help.ui import select_interactive_item


def benchmark_url(url_str: str) -> Dict[str, float]:
    """Measures network timing phases using socket/ssl."""
    parsed = urllib.parse.urlparse(url_str)
    scheme = parsed.scheme or "http"
    host = parsed.hostname or "localhost"
    port = parsed.port or (443 if scheme == "https" else 80)
    path = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query

    t0 = time.perf_counter()
    # 1. DNS Resolution
    ip = socket.gethostbyname(host)
    t_dns = time.perf_counter()

    # 2. TCP Connect
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5.0)
    sock.connect((ip, port))
    t_tcp = time.perf_counter()

    # 3. TLS Handshake (if https)
    t_tls = t_tcp
    if scheme == "https":
        ctx = ssl.create_default_context()
        sock = ctx.wrap_socket(sock, server_hostname=host)
        t_tls = time.perf_counter()

    # 4. Request send & TTFB
    req_data = f"GET {path} HTTP/1.1\r\nHost: {host}\r\nUser-Agent: Kapsel-Stat/1.0\r\nConnection: close\r\n\r\n"
    sock.sendall(req_data.encode("utf-8"))
    first_byte = sock.recv(1)
    t_ttfb = time.perf_counter()

    # 5. Content Transfer
    total_bytes = len(first_byte)
    while True:
        chunk = sock.recv(4096)
        if not chunk:
            break
        total_bytes += len(chunk)
    t_done = time.perf_counter()
    sock.close()

    return {
        "dns_ms": max(0.0, (t_dns - t0) * 1000),
        "tcp_ms": max(0.0, (t_tcp - t_dns) * 1000),
        "tls_ms": max(0.0, (t_tls - t_tcp) * 1000) if scheme == "https" else 0.0,
        "ttfb_ms": max(0.0, (t_ttfb - t_tls) * 1000),
        "transfer_ms": max(0.0, (t_done - t_ttfb) * 1000),
        "total_ms": (t_done - t0) * 1000,
        "bytes": float(total_bytes),
        "ip": ip,
    }


def render_waterfall(timings: Dict[str, float], url: str, console: Console) -> None:
    """Renders visual waterfall timing bar."""
    total = timings["total_ms"]
    dns = timings["dns_ms"]
    tcp = timings["tcp_ms"]
    tls = timings["tls_ms"]
    ttfb = timings["ttfb_ms"]
    xfer = timings["transfer_ms"]

    table = Table(title=f"HTTP Latency Waterfall: {url}", border_style="cyan", header_style="bold #00f0ff")
    table.add_column("Phase", style="bold white", width=18)
    table.add_column("Duration (ms)", style="bold #fbbf24", justify="right", width=14)
    table.add_column("Visual Proportion", style="#38bdf8")

    def _bar(ms: float) -> str:
        ratio = (ms / max(1.0, total))
        length = int(ratio * 35)
        return "█" * max(1 if ms > 0 else 0, length)

    table.add_row("DNS Lookup", f"{dns:.1f} ms", _bar(dns))
    table.add_row("TCP Handshake", f"{tcp:.1f} ms", _bar(tcp))
    if tls > 0:
        table.add_row("TLS Handshake", f"{tls:.1f} ms", _bar(tls))
    table.add_row("Server Processing (TTFB)", f"{ttfb:.1f} ms", _bar(ttfb))
    table.add_row("Content Transfer", f"{xfer:.1f} ms", _bar(xfer))
    table.add_row("[bold #10b981]Total Elapsed[/]", f"[bold #10b981]{total:.1f} ms[/]", f"Total: {total:.1f} ms ({timings['bytes'] / 1024:.1f} KB)")

    console.print(table)


def handle_stat(args: List[str], console: Optional[Console] = None) -> int:
    """
    Handles 'kps help stat <url>'
    """
    con = console or Console(legacy_windows=False)
    if not args:
        con.print("[yellow]Usage: kps help stat <url>[/yellow]")
        return 1

    url = args[0]
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    # Try external httpstat if available and non-interactive
    httpstat_bin = shutil.which("httpstat")
    if httpstat_bin and not sys.stdin.isatty():
        try:
            return subprocess.run([httpstat_bin, url]).returncode
        except Exception:
            pass

    while True:
        con.print(f"[dim]Measuring HTTP timing for [/][bold cyan]{url}[/][dim]...[/]")
        try:
            timings = benchmark_url(url)
            render_waterfall(timings, url, con)
        except Exception as e:
            con.print(f"[bold red]✖ Measurement failed:[/] {e}")
            return 1

        if not sys.stdin.isatty():
            break

        menu_items = [
            {"label": "Re-test URL Latency", "desc": "Run benchmark again", "tag": "RETRY", "action": "retry"},
            {"label": "Exit", "desc": "Finish latency inspection", "tag": "EXIT", "action": "exit"},
        ]

        selection = select_interactive_item(
            menu_items,
            title="⚡ HTTP Stat Action:",
            key_labels=[("[Enter]", "Select"), ("[Esc]", "Exit")],
        )

        if not selection or menu_items[selection[0]]["action"] == "exit":
            break

    return 0
