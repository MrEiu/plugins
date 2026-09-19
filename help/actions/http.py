"""
HTTP Request Client for Help Plugin.
Executes HTTP/HTTPS requests with rich status & body rendering, retry action,
and saving responses to files.
All comments and docstrings are in English.
"""

import json
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

try:
    from ..ui import copy_to_clipboard, select_interactive_item
except ImportError:
    from plugins.help.ui import copy_to_clipboard, select_interactive_item


def execute_http_request(url: str, method: str = "GET", headers: Optional[Dict[str, str]] = None, timeout: float = 10.0) -> Tuple[int, Dict[str, str], str]:
    """Executes an HTTP request using Python stdlib urllib."""
    hdrs = headers or {"User-Agent": "Kapsel-Help-Client/1.0"}
    req = urllib.request.Request(url, headers=hdrs, method=method)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.status
            resp_headers = dict(resp.headers)
            body = resp.read().decode("utf-8", errors="replace")
            return status, resp_headers, body
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        return e.code, dict(e.headers), body
    except Exception as e:
        return 0, {}, str(e)


def handle_http(args: List[str], console: Optional[Console] = None) -> int:
    """
    Handles 'kps help http <url>' or auto-inferred 'help https://...'
    """
    con = console or Console(legacy_windows=False)
    if not args:
        con.print("[yellow]Usage: kps help http <url> [method][/yellow]")
        return 1

    url = args[0]
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    method = "GET"
    if len(args) >= 2 and args[1].upper() in ("GET", "POST", "PUT", "DELETE", "HEAD", "PATCH"):
        method = args[1].upper()

    # Preferred tool: xh / curl if non-interactive
    xh_bin = shutil.which("xh")
    if xh_bin and not sys.stdin.isatty():
        try:
            return subprocess.run([xh_bin, method, url]).returncode
        except Exception:
            pass

    con.print(f"[dim]Sending {method} request to [/][bold cyan]{url}[/][dim]...[/]")
    status, headers, body = execute_http_request(url, method=method)

    if status == 0:
        con.print(f"[bold red]✖ Connection Error:[/] {body}")
        return 1

    status_color = "#10b981" if 200 <= status < 300 else ("#fbbf24" if 300 <= status < 400 else "#f43f5e")
    con.print(f"HTTP Status: [bold {status_color}]{status}[/bold {status_color}]\n")

    # Format body
    formatted_syntax = None
    is_json = False
    try:
        parsed = json.loads(body)
        pretty = json.dumps(parsed, indent=2, ensure_ascii=False)
        formatted_syntax = Syntax(pretty[:4000], "json", theme="monokai", line_numbers=False)
        is_json = True
    except Exception:
        preview_body = body[:2000] + ("\n... (truncated)" if len(body) > 2000 else "")
        formatted_syntax = Syntax(preview_body, "text", theme="monokai", line_numbers=False)

    con.print(Panel(formatted_syntax, title="Response Body", border_style="cyan"))

    # Interactive Action Flow
    if sys.stdin.isatty():
        while True:
            menu_items = [
                {
                    "label": "Retry Request",
                    "desc": f"Re-send {method} request to {url}",
                    "tag": "RETRY",
                    "action": "retry",
                },
                {
                    "label": "Save Response to File",
                    "desc": "Write response content to disk (e.g. response.json)",
                    "tag": "SAVE",
                    "action": "save",
                },
                {
                    "label": "Copy Body to Clipboard",
                    "desc": "Copy complete response text",
                    "tag": "COPY",
                    "action": "copy",
                },
                {
                    "label": "Exit",
                    "desc": "Close HTTP viewer",
                    "tag": "EXIT",
                    "action": "exit",
                },
            ]

            selection = select_interactive_item(
                menu_items,
                title="⚡ HTTP Action Menu:",
                key_labels=[("[Enter]", "Select"), ("[Esc]", "Done")],
            )

            if not selection:
                break

            idx, _ = selection
            act = menu_items[idx]["action"]

            if act == "retry":
                con.print(f"[dim]Re-requesting {url}...[/dim]")
                status, headers, body = execute_http_request(url, method=method)
                con.print(f"HTTP Status: [bold {status_color}]{status}[/bold {status_color}]")
            elif act == "save":
                filename = "response.json" if is_json else "response.txt"
                try:
                    Path(filename).write_text(body, encoding="utf-8")
                    con.print(f"[bold green]✔ Successfully saved response to:[/] [cyan]{filename}[/cyan]")
                except Exception as e:
                    con.print(f"[bold red]✖ Failed to save file:[/] {e}")
            elif act == "copy":
                if copy_to_clipboard(body):
                    con.print("[bold green]✔ Copied response body to clipboard![/bold green]")
            elif act == "exit":
                break

    return 0
