"""
AI-Driven Carapace Specification Generator for Kapsel AI Plugin.
Detects missing CLI tool autocompletions after command execution,
extracts help text, prompts LLM to generate standard Carapace YAML specs,
saves to ~/.kapsel/specs/{tool}.yaml, and triggers Carapace sync.

All comments and descriptions are in English.
"""

import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import threading
from typing import Optional, Set, Tuple
import yaml

from rich.console import Console
from rich.panel import Panel

from kapsel.completion.carapace_engine import CarapaceEngine
from kapsel.completion.spec_manager import CarapaceSpecManager, RESERVED_COLLISION_COMMANDS, get_user_specs_dir
from .client import AiClient

# In-memory session tracking to prevent duplicate AI invocations for the same tool
_PROCESSED_TOOLS: Set[str] = set()
_LOCK = threading.Lock()


def is_candidate_missing_tool(command: str, exit_code: int = 0) -> Optional[str]:
    """
    Evaluates whether a command execution indicates a valid, installed CLI tool
    that is missing an autocompletion specification in Carapace.

    Guardrails / Anti-misjudgment rules:
    1. Only successful executions (exit_code == 0) are considered.
    2. Extracts only the root executable name (e.g. 'docker' from 'docker compose up').
    3. Rejects relative/file script paths (starts with '.', '/', '\\').
    4. Rejects internal shell built-ins and collision commands (cd, dir, rm, ls, cls, etc.).
    5. Rejects Kapsel internal commands (kps, kapsel, kp).
    6. Verifies the tool actually exists on PATH via shutil.which().
    7. Checks if Carapace already supports it via has_completer_for().
    8. Checks if a user spec already exists in ~/.kapsel/specs/{tool}.yaml.
    9. Deduplicates within the current session.
    """
    if exit_code != 0:
        return None

    stripped = (command or "").strip()
    if not stripped:
        return None

    # 1. Extract root tool token
    try:
        tokens = shlex.split(stripped)
    except Exception:
        tokens = stripped.split()

    if not tokens:
        return None

    raw_root = tokens[0].strip()
    if not raw_root:
        return None

    # 2. Reject file paths or script invocations
    if "/" in raw_root or "\\" in raw_root or raw_root.startswith("."):
        return None

    # Normalize tool name (strip Windows extensions like .exe, .cmd, .bat, .ps1)
    tool = raw_root.lower()
    for ext in (".exe", ".cmd", ".bat", ".ps1"):
        if tool.endswith(ext):
            tool = tool[:-len(ext)]
            break

    if not tool:
        return None

    # 3. Reject Kapsel internal scope commands
    if tool in ("kps", "kapsel", "kp", "exit", "quit"):
        return None

    # 4. Reject shell built-ins and collision commands
    if tool in RESERVED_COLLISION_COMMANDS:
        return None

    # 5. Check session deduplication
    with _LOCK:
        if tool in _PROCESSED_TOOLS:
            return None

    # 6. Check if user custom spec file already exists
    user_specs_dir = get_user_specs_dir()
    if (user_specs_dir / f"{tool}.yaml").is_file() or (user_specs_dir / f"{tool}.yml").is_file():
        with _LOCK:
            _PROCESSED_TOOLS.add(tool)
        return None

    # 7. Check if binary exists on PATH
    which_path = shutil.which(tool)
    if not which_path:
        return None

    # 8. Check if Carapace already has a completer for this tool
    try:
        engine = CarapaceEngine()
        if engine.has_completer_for(tool):
            with _LOCK:
                _PROCESSED_TOOLS.add(tool)
            return None
    except Exception:
        pass

    # Mark as processed in session so we don't trigger repeatedly
    with _LOCK:
        _PROCESSED_TOOLS.add(tool)

    return tool


def fetch_tool_help(tool: str, timeout: float = 2.5) -> str:
    """
    Attempts to probe help documentation from the tool using standard flags.
    Returns cleaned help text truncated to a safe length for LLM context.
    """
    for flag in ["--help", "-h", "help"]:
        try:
            res = subprocess.run(
                [tool, flag],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
            combined = ((res.stdout or "") + "\n" + (res.stderr or "")).strip()
            if len(combined) >= 30:
                # Truncate to max 5000 characters to prevent prompt bloat
                return combined[:5000]
        except Exception:
            continue
    return ""


def _extract_yaml_from_response(raw: str) -> str:
    """Extracts YAML content from markdown code block if present."""
    pattern = r"```(?:yaml)?\s*([\s\S]*?)\s*```"
    matches = re.findall(pattern, raw, re.IGNORECASE)
    if matches:
        return matches[0].strip()
    return raw.strip()


def generate_carapace_spec(
    tool: str,
    client: AiClient,
    console: Optional[Console] = None,
    is_background: bool = False,
) -> Tuple[bool, str]:
    """
    Synthesizes a Carapace specification YAML using the AI client,
    validates the YAML structure, writes to ~/.kapsel/specs/{tool}.yaml,
    and calls CarapaceSpecManager to compile and hot-reload.
    Returns (success: bool, message: str).
    """
    con = console or Console(legacy_windows=False)

    help_text = fetch_tool_help(tool)
    if not help_text:
        msg = f"Could not retrieve help text for '{tool}' using --help or -h."
        if not is_background:
            con.print(f"[yellow]{msg}[/]")
        return False, msg

    system_prompt = (
        "You are an expert CLI autocompletion engineer specializing in Carapace specifications.\n"
        "Generate a declarative Carapace specification YAML for the CLI tool based on its help text.\n\n"
        "Carapace Specification Schema Rules:\n"
        "1. Root element must have `name: <tool>` and a one-line `description`.\n"
        "2. Top-level CLI flags must be listed under `flags:` as a key-value dictionary.\n"
        "   Example:\n"
        "     flags:\n"
        "       -h, --help: Show help information\n"
        "       -v, --version: Show version number\n"
        "3. Subcommands (if any) must be listed under `commands:` as a list of mappings, each containing `name`, `description`, optional `flags`, and optional sub-`commands`.\n"
        "4. DO NOT invent arbitrary commands; only extract real flags and subcommands found in the provided help text.\n"
        "5. Output ONLY the raw YAML enclosed in a ```yaml ... ``` code block. No explanations, no markdown outside the block."
    )

    user_prompt = f"Tool: {tool}\n\nHelp Text:\n{help_text}"

    try:
        response_text = client.chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
        )

        yaml_str = _extract_yaml_from_response(response_text)
        if not yaml_str:
            return False, "AI returned empty response."

        data = yaml.safe_load(yaml_str)
        if not isinstance(data, dict):
            return False, "AI output is not a valid YAML mapping."

        # Ensure correct name
        data["name"] = tool
        if "description" not in data or not data["description"]:
            data["description"] = f"{tool} CLI command"

        # Write to ~/.kapsel/specs/{tool}.yaml
        user_specs_dir = get_user_specs_dir()
        user_specs_dir.mkdir(parents=True, exist_ok=True)
        target_path = user_specs_dir / f"{tool}.yaml"

        with open(target_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

        # Synchronize specs to Carapace
        spec_mgr = CarapaceSpecManager()
        spec_mgr.sync_specs()

        # Invalidate CarapaceEngine cached tools list so it includes the new spec
        try:
            engine = CarapaceEngine()
            engine.reload_tools()
        except Exception:
            pass

        return True, str(target_path)

    except Exception as e:
        return False, str(e)
