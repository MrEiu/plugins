"""
Smart Intent Router for Kapsel Help Plugin.
Dispatches command queries to appropriate action workflows using explicit subcommands
or zero-friction auto-inference (e.g. 'help 8080' -> port, 'help github.com' -> dns).
All comments and docstrings are in English.
"""

import re
from typing import List, Tuple

KNOWN_SUBCOMMANDS = {
    "port": "port",
    "ports": "port",
    "ps": "ps",
    "proc": "ps",
    "procs": "ps",
    "top": "ps",
    "kill": "kill",
    "which": "which",
    "where": "which",
    "find": "which",
    "locate": "which",
    "dns": "dns",
    "dig": "dns",
    "nslookup": "dns",
    "http": "http",
    "curl": "http",
    "xh": "http",
    "stat": "stat",
    "httpstat": "stat",
    "bench": "stat",
    "sys": "sys",
    "sysinfo": "sys",
    "os": "sys",
    "specs": "sys",
    "fastfetch": "sys",
    "cheat": "cheat",
    "tldr": "cheat",
    "install": "install",
    "setup": "install",
}


def infer_help_intent(raw_args: List[str]) -> Tuple[str, List[str]]:
    """
    Infers the intended action workflow from command arguments.
    Returns (action_type, forwarded_args).
    """
    if not raw_args:
        return "guide", []

    first = raw_args[0].strip()
    first_lower = first.lower()

    # 1. Guide check
    if first_lower in ("-h", "--help") and len(raw_args) == 1:
        return "guide", []

    # 2. Explicit Subcommands check
    if first_lower in KNOWN_SUBCOMMANDS:
        action = KNOWN_SUBCOMMANDS[first_lower]
        return action, raw_args[1:]

    # 3. Smart Auto-Inference:
    # A. Port: e.g. ":8080" or "8080", "3000", "5432"
    if first.startswith(":") and first[1:].isdigit():
        port_num = int(first[1:])
        if 1 <= port_num <= 65535:
            return "port", [str(port_num)] + raw_args[1:]

    if first.isdigit():
        port_num = int(first)
        if 1 <= port_num <= 65535:
            return "port", raw_args

    # B. HTTP Request: starts with http:// or https://
    if first_lower.startswith(("http://", "https://")):
        return "http", raw_args

    # C. PID direct kill prefix: 'pid:1234'
    if first_lower.startswith("pid:") and first_lower[4:].isdigit():
        return "kill", [first_lower[4:]]

    # D. IP address: e.g. "8.8.8.8", "127.0.0.1", "1.1.1.1"
    if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", first):
        return "dns", raw_args

    # E. Domain name: contains dot, valid domain format, not a code/script file extension
    file_exts = (".exe", ".cmd", ".bat", ".sh", ".py", ".js", ".ts", ".json", ".txt", ".md", ".yml", ".yaml")
    if (
        "." in first
        and not first_lower.endswith(file_exts)
        and re.match(r"^[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)+$", first)
    ):
        return "dns", raw_args

    # F. Default fallback: Command Usage & Examples (tldr / cheat.sh + which)
    return "cheat", raw_args
