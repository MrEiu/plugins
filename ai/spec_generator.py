"""
AI-Driven Carapace Specification Generator for Kapsel AI Plugin.
Detects missing CLI tool autocompletions after command execution,
extracts help text, prompts LLM to generate standard Carapace YAML specs,
sanitizes structure, saves to ~/.kapsel/specs/{tool}.yaml, and triggers Carapace sync.

All comments and descriptions are in English.
"""

import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import threading
from typing import Any, Dict, List, Optional, Set, Tuple
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


def _clean_help_output(raw_bytes: bytes) -> str:
    """
    Decodes process output bytes handling UTF-16LE, UTF-8, and system codepages.
    Windows native CLI tools (wsl.exe, cmd.exe, chcp, etc.) frequently emit UTF-16LE
    or OEM codepages when redirected.
    """
    if not raw_bytes:
        return ""

    # Check for UTF-16 BOM or alternating null bytes common in Windows UTF-16LE
    if raw_bytes.startswith(b"\xff\xfe") or raw_bytes.startswith(b"\xfe\xff") or (b"\x00" in raw_bytes[:100]):
        try:
            decoded = raw_bytes.decode("utf-16le", errors="replace")
            if "\x00" not in decoded and len(decoded.strip()) > 5:
                return decoded.strip()
        except Exception:
            pass

    # Try UTF-8
    try:
        decoded = raw_bytes.decode("utf-8")
        return decoded.strip()
    except UnicodeDecodeError:
        pass

    # Try common local encodings
    for enc in ["latin1", "cp1252", "gbk", "cp936"]:
        try:
            decoded = raw_bytes.decode(enc, errors="replace")
            return decoded.strip()
        except Exception:
            continue

    return raw_bytes.decode("utf-8", errors="replace").strip()


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
                timeout=timeout,
            )
            raw = (res.stdout or b"") + b"\n" + (res.stderr or b"")
            combined = _clean_help_output(raw)
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


def sanitize_carapace_spec_dict(data: Dict[str, Any], tool_name: str) -> Dict[str, Any]:
    """
    Sanitizes and normalizes an AI-generated Carapace spec dictionary to guarantee
    100% compliance with Carapace parser requirements:
    1. Converts Windows slash flags (/s, /r, /?, /hybrid) to standard Unix dashes (-s, -r, -h, --hybrid).
    2. Strips invalid flag keys like bare '--' or empty keys.
    3. Migrates any commands starting with '-' or '/' from 'commands' into 'flags'.
    4. Ensures clean subcommands with alphanumeric names recursively.
    5. Normalizes argument completion keys in 'completion.flag' and synchronizes flag '=' indicators.
    6. Strictly avoids injecting arbitrary default positional '$files' completions.
    """
    clean: Dict[str, Any] = {}

    clean["name"] = str(data.get("name") or tool_name).strip()
    clean["description"] = str(data.get("description") or f"{tool_name} CLI command").strip()

    if "standalone" in data:
        clean["standalone"] = bool(data["standalone"])

    raw_flags = data.get("flags")
    clean_flags: Dict[str, str] = {}
    seen_shorthands: Set[str] = set()

    def _normalize_flag_key(key_str: str) -> Optional[str]:
        raw_parts = [p.strip() for p in key_str.split(",") if p.strip()]
        cleaned_parts: List[str] = []

        for p in raw_parts:
            # Handle Windows slash flags: /s -> -s, /help -> --help, /? -> --help
            if p.startswith("/"):
                tail = p[1:].strip()
                if tail == "?":
                    p = "--help"
                elif len(tail) == 1:
                    p = f"-{tail}"
                else:
                    p = f"--{tail}"
            elif not p.startswith("-"):
                if len(p) == 1:
                    p = f"-{p}"
                else:
                    p = f"--{p}"

            # Preserve argument indicators if present
            has_arg = p.endswith(":") or p.endswith("=")
            has_optarg = p.endswith("?")
            base_p = p.rstrip(":=?").strip()

            if not base_p or base_p in ("--", "-"):
                continue

            # Deduplicate shorthands: if -x is already claimed by another flag, drop duplicate
            if base_p.startswith("-") and not base_p.startswith("--") and len(base_p) == 2:
                shorthand_letter = base_p[1]
                if shorthand_letter in seen_shorthands:
                    continue
                seen_shorthands.add(shorthand_letter)

            if has_arg:
                rebuilt = base_p + "="
            elif has_optarg:
                rebuilt = base_p + "?"
            else:
                rebuilt = base_p

            cleaned_parts.append(rebuilt)

        if not cleaned_parts:
            return None

        # Carapace requirement: short flag MUST come before long flag (e.g. "-e, --exec", NOT "--exec, -e")
        cleaned_parts.sort(key=lambda x: (len(x.split("=")[0].split("?")[0]), x))
        return ", ".join(cleaned_parts)

    if isinstance(raw_flags, dict):
        for raw_k, raw_v in raw_flags.items():
            norm_k = _normalize_flag_key(str(raw_k))
            if norm_k:
                clean_flags[norm_k] = str(raw_v or "").strip()

    raw_commands = data.get("commands")
    clean_commands: List[Dict[str, Any]] = []

    if isinstance(raw_commands, list):
        for cmd in raw_commands:
            if not isinstance(cmd, dict):
                continue
            c_name = str(cmd.get("name", "")).strip()
            if not c_name:
                continue

            # If subcommand name starts with '-' or '/', it is actually a flag mistakenly classified as command
            if c_name.startswith("-") or c_name.startswith("/"):
                norm_flag = _normalize_flag_key(c_name)
                if norm_flag:
                    clean_flags[norm_flag] = str(cmd.get("description", "")).strip()
                # Also migrate its sub-flags if present
                sub_f = cmd.get("flags")
                if isinstance(sub_f, dict):
                    for sf_k, sf_v in sub_f.items():
                        norm_sf = _normalize_flag_key(str(sf_k))
                        if norm_sf:
                            clean_flags[norm_sf] = str(sf_v or "").strip()
                continue

            # Recursively sanitize clean subcommands
            sanitized_sub = sanitize_carapace_spec_dict(cmd, c_name)
            clean_commands.append(sanitized_sub)

    # Sanitize completion section
    raw_completion = data.get("completion")
    clean_completion: Dict[str, Any] = {}

    if isinstance(raw_completion, dict):
        # 1. Flag argument completion
        raw_flag_comp = raw_completion.get("flag")
        if isinstance(raw_flag_comp, dict):
            clean_flag_comp: Dict[str, List[str]] = {}
            for fk, fvals in raw_flag_comp.items():
                if not isinstance(fvals, list):
                    continue
                clean_fk = str(fk).strip()
                if "," in clean_fk:
                    clean_fk = clean_fk.split(",")[-1].strip()
                clean_fk = clean_fk.lstrip("-/").rstrip(":=?").strip()
                if not clean_fk:
                    continue
                clean_vals = [str(v) for v in fvals if v is not None]
                if clean_vals:
                    clean_flag_comp[clean_fk] = clean_vals

            if clean_flag_comp:
                clean_completion["flag"] = clean_flag_comp

        # 2. Positional argument completion
        raw_pos = raw_completion.get("positional")
        if isinstance(raw_pos, list) and raw_pos:
            clean_pos: List[List[str]] = []
            for p_item in raw_pos:
                if isinstance(p_item, list):
                    clean_pos.append([str(v) for v in p_item if v is not None])
            if clean_pos:
                clean_completion["positional"] = clean_pos

        # 3. Positionalany argument completion
        raw_pos_any = raw_completion.get("positionalany")
        if isinstance(raw_pos_any, list) and raw_pos_any:
            clean_completion["positionalany"] = [str(v) for v in raw_pos_any if v is not None]

    # Flag-Argument Synchronization:
    # If an option has completion candidates under completion.flag.<name>,
    # ensure the flag definition in clean_flags ends with '=' so Carapace
    # recognizes it as accepting an argument and activates the completion.
    # NOTE: Carapace's '?' modifier requires attached '--flag=val' and returns
    # empty candidates on space-separated '--flag <TAB>'. Therefore, flags with
    # candidate completions MUST end with '=', converting any accidental '?' to '='.
    if "flag" in clean_completion:
        new_flags: Dict[str, str] = {}
        for f_key, f_desc in clean_flags.items():
            parts = [p.strip() for p in f_key.split(",") if p.strip()]
            needs_arg = False
            for p in parts:
                bare = p.lstrip("-").rstrip(":=?").strip()
                if bare in clean_completion["flag"]:
                    needs_arg = True
                    break

            if needs_arg:
                parts[-1] = parts[-1].rstrip("?")
                if not parts[-1].endswith("="):
                    parts[-1] = parts[-1] + "="
                new_key = ", ".join(parts)
                new_flags[new_key] = f_desc
            else:
                new_flags[f_key] = f_desc
        clean_flags = new_flags

    if clean_flags:
        clean["flags"] = clean_flags

    if clean_commands:
        clean["commands"] = clean_commands

    if clean_completion:
        clean["completion"] = clean_completion

    return clean


def sanitize_all_user_specs() -> int:
    """
    Sanitizes all YAML spec files in the user specs directory (~/.kapsel/specs or KPS-data/specs)
    and synchronizes them into Carapace. Strips obsolete $files fallbacks and ensures
    compliance with Carapace parser requirements.
    """
    user_specs_dir = get_user_specs_dir()
    if not user_specs_dir.is_dir():
        return 0

    count = 0
    for p in user_specs_dir.glob("*.yaml"):
        if not p.is_file():
            continue
        try:
            with open(p, "r", encoding="utf-8") as f:
                content = f.read()
            data = yaml.safe_load(content)
            if isinstance(data, dict):
                cleaned = sanitize_carapace_spec_dict(data, p.stem)
                new_yaml = yaml.dump(cleaned, allow_unicode=True, default_flow_style=False, sort_keys=False)
                if new_yaml != content:
                    with open(p, "w", encoding="utf-8") as f:
                        f.write(new_yaml)
                    count += 1
        except Exception:
            pass

    if count > 0:
        spec_mgr = CarapaceSpecManager()
        spec_mgr.sync_specs(force=True)
        try:
            engine = CarapaceEngine()
            engine.reload_tools()
        except Exception:
            pass

    return count


def generate_carapace_spec(
    tool: str,
    client: AiClient,
    console: Optional[Console] = None,
    is_background: bool = False,
) -> Tuple[bool, str]:
    """
    Synthesizes a Carapace specification YAML using the AI client,
    sanitizes the YAML structure, writes to ~/.kapsel/specs/{tool}.yaml,
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
        "STRICT Carapace Specification Schema Rules:\n"
        "1. Root element MUST have `name: <tool>` and a one-line `description`.\n"
        "2. All CLI flags MUST be listed under `flags:` as a key-value mapping.\n"
        "   - Every flag key MUST start with `-` (short flag, e.g. `-v`, `-h`) or `--` (long flag, e.g. `--version`, `--help`).\n"
        "   - CRITICAL Flag Argument Suffix (= vs ?):\n"
        "     * ALWAYS use `=` for ANY flag that accepts an argument/value (e.g. `--install=`, `-d, --distribution=`, `-u, --user=`, `-o, --output=`, `-f, --format=`), EVEN IF help text displays brackets like `[distro]` or `[value]`.\n"
        "       In Carapace, `=` enables both space-separated argument completion (`--install <TAB>`) and attached syntax (`--install=<TAB>`).\n"
        "     * NEVER use `?` for options where users type space-separated arguments (like `wsl --install <distro>`). In Carapace, `?` strictly requires attached `=` syntax (`--flag=value`) and will yield ZERO candidates when users type `--flag <SPACE><TAB>`.\n"
        "     * If a flag is a pure BOOLEAN switch (takes no arguments at all), DO NOT append `=` or `?` (e.g. `-h, --help`, `-v, --version`, `--status`, `--all`, `--verbose`).\n"
        "   - Short flag MUST precede long flag (e.g. `-d, --distribution=`, NOT `--distribution=, -d`).\n"
        "   - CRITICAL: DO NOT use Windows slash syntax (e.g. `/s`, `/r`, `/?`). Convert them to standard dashes (`-s`, `-r`, `-h, --help`).\n"
        "   - CRITICAL: Never use bare `--` or `-` as a flag key.\n"
        "3. Subcommands (if any) MUST be listed under `commands:` as a list of mappings.\n"
        "   - Each subcommand MUST have an alphanumeric `name` (e.g. `status`, `run`, `list`, `build`).\n"
        "   - Subcommand names MUST NOT start with `-` or `--`. Options like `--install` are flags, NOT subcommands!\n"
        "4. Argument-Specific Completion (`completion:` mapping):\n"
        "   - To provide completions for flag arguments, define them under `completion.flag.<flag_name>`.\n"
        "     * Use the bare flag name without leading dashes (e.g. `install`, `distribution`, `format`, `user`).\n"
        "     * Provide a list of completion candidates, each formatted with tab-separated descriptions: `[\"value\\tdescription\"]`.\n"
        "     * For flags with known choices (such as distributions, formats, log-levels, shells, modes), extract or provide common valid values.\n"
        "     * For flags that accept file paths, use `[\"$files\"]`.\n"
        "     * For flags that accept directory paths, use `[\"$directories\"]`.\n"
        "     * DO NOT use `$files` for options that take non-file values (like distributions, usernames, URLs, formats)!\n"
        "   - If the tool or subcommand takes positional arguments, specify them under `completion.positional` as a list of lists.\n"
        "     * DO NOT automatically inject `[\"$files\"]` unless the command explicitly expects files.\n"
        "5. Canonical Example for reference:\n"
        "   ```yaml\n"
        "   name: wsl\n"
        "   description: Windows Subsystem for Linux\n"
        "   flags:\n"
        "     -d, --distribution=: Run the specified distribution\n"
        "     --install=: Install a Linux distribution\n"
        "     -u, --user=: Run as specified user\n"
        "     --status: Show WSL status\n"
        "     -h, --help: Show help information\n"
        "   completion:\n"
        "     flag:\n"
        "       distribution: [\"Ubuntu\\tUbuntu Linux\", \"Debian\\tDebian GNU/Linux\", \"kali-linux\\tKali Linux Rolling\", \"openSUSE-Leap-15.5\\topenSUSE Leap\"]\n"
        "       install: [\"Ubuntu\\tUbuntu Linux\", \"Debian\\tDebian GNU/Linux\", \"kali-linux\\tKali Linux Rolling\", \"openSUSE-Leap-15.5\\topenSUSE Leap\"]\n"
        "       user: [\"root\\tSuperuser\"]\n"
        "   ```\n"
        "6. Output ONLY the raw YAML enclosed in a ```yaml ... ``` code block. No explanations, no markdown outside the block."
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

        # Programmatically sanitize and normalize the spec dictionary
        cleaned_data = sanitize_carapace_spec_dict(data, tool)

        # Write to ~/.kapsel/specs/{tool}.yaml
        user_specs_dir = get_user_specs_dir()
        user_specs_dir.mkdir(parents=True, exist_ok=True)
        target_path = user_specs_dir / f"{tool}.yaml"

        with open(target_path, "w", encoding="utf-8") as f:
            yaml.dump(cleaned_data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

        # Synchronize specs to Carapace and sanitize any existing user specs
        sanitize_all_user_specs()
        spec_mgr = CarapaceSpecManager()
        spec_mgr.sync_specs(force=True)

        # Invalidate CarapaceEngine cached tools list so it includes the new spec
        try:
            engine = CarapaceEngine()
            engine.reload_tools()
        except Exception:
            pass

        return True, str(target_path)

    except Exception as e:
        return False, str(e)
