"""
DNS and Network Domain Resolver for Help Plugin.
Inspects DNS records, performs reverse DNS lookups, and probes HTTP connectivity.
All comments and docstrings are in English.
"""

from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

try:
    from ..ui import copy_to_clipboard, select_interactive_item
except ImportError:
    from plugins.help.ui import copy_to_clipboard, select_interactive_item


def resolve_domain_ips(domain: str) -> List[Dict[str, str]]:
    """Resolves IPv4 and IPv6 addresses using stdlib socket."""
    results: List[Dict[str, str]] = []
    seen = set()
    try:
        infos = socket.getaddrinfo(domain, 80, proto=socket.IPPROTO_TCP)
        for family, _, _, _, sockaddr in infos:
            ip = sockaddr[0]
            if ip not in seen:
                seen.add(ip)
                family_name = "IPv4" if family == socket.AF_INET else "IPv6"
                results.append({"family": family_name, "ip": ip})
    except Exception:
        pass
    return results


def resolve_reverse_ptr(ip_or_domain: str) -> str:
    """Performs reverse DNS lookup."""
    try:
        name, _, _ = socket.gethostbyaddr(ip_or_domain)
        return name
    except Exception:
        return "Not available"


def probe_http_connectivity(domain: str, timeout: float = 3.0) -> Tuple[bool, str]:
    """Probes HTTP and HTTPS connectivity for the domain."""
    for scheme in ("https://", "http://"):
        target_url = f"{scheme}{domain}"
        try:
            req = urllib.request.Request(target_url, headers={"User-Agent": "Kapsel-DNS-Probe/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return True, f"HTTP {resp.status} OK ({scheme.rstrip(':/')})"
        except urllib.error.HTTPError as e:
            return True, f"HTTP {e.code} {e.reason} ({scheme.rstrip(':/')})"
        except Exception:
            continue
    return False, "Failed to connect"


def handle_dns(args: List[str], console: Optional[Console] = None) -> int:
    """
    Handles 'kps help dns <domain>' or auto-inferred 'help github.com' / 'help 8.8.8.8'
    """
    con = console or Console(legacy_windows=False)
    if not args:
        con.print("[yellow]Usage: kps help dns <domain or IP>[/yellow]")
        return 1

    target = args[0].strip().rstrip("/")
    if target.startswith(("http://", "https://")):
        target = target.split("://")[1].split("/")[0]

    # Check if doggo CLI is installed and non-interactive
    doggo_bin = shutil.which("doggo")
    if doggo_bin and not sys.stdin.isatty():
        try:
            return subprocess.run([doggo_bin, target]).returncode
        except Exception:
            pass

    con.print(f"[dim]Resolving DNS for [/][bold cyan]{target}[/][dim]...[/]")
    is_ip = bool(re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", target))

    if is_ip:
        reverse_name = resolve_reverse_ptr(target)
        con.print(
            Panel(
                f"[bold white]IP Address:[/] [bold cyan]{target}[/bold cyan]\n"
                f"[bold white]Reverse PTR Hostname:[/] [bold yellow]{reverse_name}[/bold yellow]",
                title="Reverse DNS Lookup",
                border_style="cyan",
            )
        )
        return 0

    ips = resolve_domain_ips(target)
    if not ips:
        con.print(f"[bold red]✖ Unable to resolve domain '{target}'.[/bold red]")
        return 1

    table = Table(title=f"DNS Records for {target}", border_style="cyan", header_style="bold #00f0ff")
    table.add_column("Type", style="bold #38bdf8", width=8)
    table.add_column("IP Address", style="bold white")

    for rec in ips:
        table.add_row(rec["family"], rec["ip"])

    con.print(table)

    # Interactive Action Flow
    if sys.stdin.isatty():
        primary_ip = ips[0]["ip"]
        menu_items = [
            {
                "label": f"Probe HTTP/HTTPS connectivity ({target})",
                "desc": "Check web server responsiveness",
                "tag": "HTTP",
                "action": "probe",
            },
            {
                "label": f"Copy Primary IP ({primary_ip})",
                "desc": "Copy resolved IP to system clipboard",
                "tag": "COPY",
                "action": "copy",
            },
            {
                "label": f"Reverse DNS Lookup for {primary_ip}",
                "desc": "Query PTR hostname",
                "tag": "PTR",
                "action": "ptr",
            },
            {
                "label": "Exit",
                "desc": "Close DNS query",
                "tag": "EXIT",
                "action": "exit",
            },
        ]

        selection = select_interactive_item(
            menu_items,
            title=f"⚡ Action for {target}:",
            key_labels=[("[Enter]", "Select"), ("[Esc]", "Exit")],
        )

        if selection:
            idx, _ = selection
            act = menu_items[idx]["action"]
            if act == "probe":
                con.print(f"[dim]Probing HTTP/HTTPS for {target}...[/dim]")
                ok, status_msg = probe_http_connectivity(target)
                if ok:
                    con.print(f"[bold green]✔ Server Responding:[/] {status_msg}")
                else:
                    con.print(f"[bold red]✖ Connectivity Check Failed:[/] {status_msg}")
            elif act == "copy":
                if copy_to_clipboard(primary_ip):
                    con.print(f"[bold green]✔ Copied IP to clipboard:[/] [cyan]{primary_ip}[/cyan]")
            elif act == "ptr":
                ptr_name = resolve_reverse_ptr(primary_ip)
                con.print(f"[bold white]Reverse PTR for {primary_ip}:[/] [bold yellow]{ptr_name}[/bold yellow]")

    return 0
