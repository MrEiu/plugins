"""
Kapsel AI Plugin - Specialized Terminal Action Implementations.
Contains pure terminal interactive workflows:
1. Natural language to command (with Enter to run / Tab to copy / Esc to cancel)
2. Command parameter dissection & explanation (explain)
3. One-click error diagnosis & auto-fix from BlockRegistry (fix / ?)
4. Git diff to conventional commit with one-click commit (commit)
5. Pipe / Stdin stream analysis
6. Workspace project scout & intelligence (scout)
All comments and descriptions are in English.
"""

import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.panel import Panel

from kapsel.ui.prompt import copy_to_clipboard
from .client import AiClient


def get_terminal_context() -> Dict[str, str]:
    """Inspects the current system, shell, and working directory."""
    os_name = "Windows" if sys.platform == "win32" else ("macOS" if sys.platform == "darwin" else "Linux")
    from kapsel.core.detector import detector
    shell_name, shell_path = detector.detect_shell()
    return {
        "os": os_name,
        "shell": shell_name.lower(),
        "shell_path": shell_path or shell_name,
        "cwd": str(Path.cwd()),
    }


def prompt_action_choice(command: str, con: Console) -> str:
    """
    Displays the generated command and asks the user for confirmation:
    Returns 'run', 'copy', or 'cancel'.
    """
    con.print("\n[bold #00f0ff]🤖 建议指令:[/]")
    con.print(f"   [bold #10b981]{command}[/]\n")
    con.print("[dim]操作:[/] [bold green][Enter][/] 直接运行  [bold yellow][e / Tab][/] 复制到剪贴板  [bold red][q / Esc][/] 取消")

    try:
        choice = input("❯ ").strip().lower()
        if choice in ("", "y", "yes"):
            return "run"
        elif choice in ("e", "edit", "tab", "c"):
            return "copy"
        else:
            return "cancel"
    except (KeyboardInterrupt, EOFError):
        return "cancel"


def action_do(
    prompt_text: str,
    con: Console,
    client: AiClient,
    executor: Optional[Any] = None,
) -> int:
    """Translates natural language to exact shell command and interactively confirms."""
    ctx = get_terminal_context()
    sys_prompt = f"""You are Kapsel CLI Copilot, an expert terminal command generator.
Target Operating System: {ctx['os']}
Target Shell: {ctx['shell']}
Current Directory: {ctx['cwd']}

Convert the user's natural language request into the SINGLE exact, working executable command for {ctx['shell']} on {ctx['os']}.
CRITICAL RULES:
1. Output ONLY the raw command on the FIRST line. Do NOT use markdown fences (no ```).
2. On the SECOND line, output a single-line summary starting with '# info: '.
3. Never output Linux-only commands (like grep, ls) when running on Windows PowerShell unless specifically asked; use PowerShell native cmdlets or aliases.
"""

    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": prompt_text},
    ]

    con.print("[dim]Thinking...[/]")
    try:
        raw_res = client.chat_completion(messages, temperature=0.1)
    except Exception as e:
        con.print(f"[bold #f43f5e]AI Error:[/] {e}\n")
        return 1

    lines = [line.strip() for line in raw_res.strip().splitlines() if line.strip()]
    if not lines:
        con.print("[yellow]AI did not generate a command.[/]\n")
        return 0

    command = lines[0]
    # Clean possible markdown wrapping if model output it
    if command.startswith("```"):
        command = command.strip("`").strip()
    if command.startswith(f"{ctx['shell']}"):
        command = command.split(" ", 1)[-1].strip()

    info = lines[1] if len(lines) > 1 and lines[1].startswith("# info:") else ""
    if info:
        con.print(f"[dim]{info}[/]")

    decision = prompt_action_choice(command, con)
    if decision == "run":
        con.print(f"[dim]Executing:[/] [bold cyan]{command}[/]\n")
        if executor:
            return executor.execute(command).exit_code
        else:
            return subprocess.run(command, shell=True).returncode
    elif decision == "copy":
        if copy_to_clipboard(command):
            con.print("[bold #10b981]✔ Command copied to clipboard![/] [dim]Press Ctrl+V to paste and edit.[/]\n")
        else:
            con.print(f"[yellow]Could not access clipboard. Command is:[/] {command}\n")
        return 0
    else:
        con.print("[dim]Cancelled.[/]\n")
        return 0


def action_fix(
    con: Console,
    client: AiClient,
    executor: Optional[Any] = None,
) -> int:
    """Diagnoses the last failed command from BlockRegistry and proposes an auto-fix."""
    from kapsel.core.block.registry import get_block_registry

    reg = get_block_registry()
    blocks = reg.get_blocks()

    # Find the latest failed block, or fallback to the latest block
    target_block = None
    for b in reversed(blocks):
        if b.exit_code != 0:
            target_block = b
            break

    if not target_block and blocks:
        target_block = blocks[-1]

    if not target_block:
        con.print("[yellow]No command execution history found to diagnose.[/]\n")
        return 0

    ctx = get_terminal_context()
    con.print(f"\n[bold #00f0ff]🔍 Diagnosing last failed command:[/] [bold white]{target_block.command}[/] [dim](exit {target_block.exit_code})[/]")

    sys_prompt = f"""You are Kapsel CLI Error Diagnostic Assistant.
Operating System: {ctx['os']}
Target Shell: {ctx['shell']}
Working Directory: {target_block.cwd}

Analyze the failed command and error output.
1. Explain the root cause in 1-2 concise sentences.
2. Provide the EXACT command to fix or recover from the error on a single line prefixed with 'FIX_CMD: <command>'.
Do NOT use markdown code blocks.
"""

    user_msg = f"""Command executed:
{target_block.command}

Exit Code: {target_block.exit_code}

Output / Error Message:
{target_block.output_text or '(No stderr captured)'}
"""

    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": user_msg},
    ]

    con.print("[dim]Analyzing failure causes...[/]")
    try:
        res = client.chat_completion(messages, temperature=0.1)
    except Exception as e:
        con.print(f"[bold #f43f5e]AI Error:[/] {e}\n")
        return 1

    # Parse FIX_CMD
    explanation_lines = []
    fix_cmd = ""
    for line in res.splitlines():
        if line.strip().startswith("FIX_CMD:"):
            fix_cmd = line.split("FIX_CMD:", 1)[1].strip()
        else:
            explanation_lines.append(line)

    con.print(f"\n[bold #f59e0b]💡 诊断分析:[/]\n" + "\n".join(explanation_lines).strip())

    if fix_cmd:
        decision = prompt_action_choice(fix_cmd, con)
        if decision == "run":
            con.print(f"[dim]Running fix:[/] [bold cyan]{fix_cmd}[/]\n")
            if executor:
                return executor.execute(fix_cmd).exit_code
            else:
                return subprocess.run(fix_cmd, shell=True).returncode
        elif decision == "copy":
            copy_to_clipboard(fix_cmd)
            con.print("[bold #10b981]✔ Fix command copied to clipboard![/]\n")
            return 0
        else:
            con.print("[dim]Cancelled.[/]\n")
            return 0
    else:
        con.print("\n[dim]No specific auto-fix command proposed.[/]\n")
        return 0


def action_commit(con: Console, client: AiClient) -> int:
    """Inspects git diff and generates a conventional commit message with interactive confirmation."""
    if not shutil.which("git"):
        con.print("[bold #f43f5e]Error:[/] git is not installed or not in PATH.\n")
        return 1

    # Check staged changes
    staged = subprocess.run(["git", "diff", "--cached"], capture_output=True, text=True).stdout.strip()
    diff_to_analyze = staged
    is_staged = bool(staged)

    if not diff_to_analyze:
        # Check unstaged changes
        unstaged = subprocess.run(["git", "diff"], capture_output=True, text=True).stdout.strip()
        if unstaged:
            con.print("[yellow]Notice:[/] No staged changes found. Analyzing unstaged changes...")
            diff_to_analyze = unstaged
        else:
            status = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True).stdout.strip()
            if status:
                con.print(f"[dim]Found untracked / unindexed files:\n{status}[/]\n")
                con.print("Stage all changes with [bold cyan]git add -A[/]? (y/n): ", end="")
                ans = input().strip().lower()
                if ans in ("y", "yes"):
                    subprocess.run(["git", "add", "-A"])
                    diff_to_analyze = subprocess.run(["git", "diff", "--cached"], capture_output=True, text=True).stdout.strip()
                    is_staged = True
                else:
                    return 0
            else:
                con.print("[bold #10b981]✔ Working directory clean. Nothing to commit.[/]\n")
                return 0

    con.print("[dim]Generating conventional commit message from git diff...[/]")

    sys_prompt = """You are an expert Git commit message generator following Conventional Commits format (feat, fix, docs, refactor, style, test, chore, perf).
Analyze the git diff and output ONLY the single-line commit message on the first line (e.g. feat(auth): add JWT login authentication).
If needed, add a brief 1-2 sentence description on subsequent lines.
Do NOT output markdown code blocks or conversational chatter.
"""

    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": f"Git Diff:\n{diff_to_analyze[:6000]}"},
    ]

    try:
        res = client.chat_completion(messages, temperature=0.1).strip()
    except Exception as e:
        con.print(f"[bold #f43f5e]AI Error:[/] {e}\n")
        return 1

    commit_msg = res.splitlines()[0].strip("`").strip()

    con.print(f"\n[bold #00f0ff]🤖 建议 Commit 消息:[/]")
    con.print(f"   [bold #10b981]{commit_msg}[/]\n")
    con.print("[dim]操作:[/] [bold green][Enter][/] 执行提交  [bold yellow][e / Tab][/] 复制提交语  [bold red][q / Esc][/] 取消")

    try:
        choice = input("❯ ").strip().lower()
        if choice in ("", "y", "yes"):
            if not is_staged:
                subprocess.run(["git", "add", "-A"])
            proc = subprocess.run(["git", "commit", "-m", commit_msg])
            if proc.returncode == 0:
                con.print(f"[bold #10b981]✔ Successfully committed changes![/]\n")
            return proc.returncode
        elif choice in ("e", "edit", "c", "tab"):
            copy_to_clipboard(commit_msg)
            con.print("[bold #10b981]✔ Commit message copied to clipboard![/]\n")
            return 0
        else:
            con.print("[dim]Cancelled.[/]\n")
            return 0
    except (KeyboardInterrupt, EOFError):
        con.print("\n[dim]Cancelled.[/]\n")
        return 0


def action_explain(command_text: str, con: Console, client: AiClient) -> int:
    """Dissects and explains a terminal command and its flags."""
    ctx = get_terminal_context()
    target_cmd = command_text.strip()

    if not target_cmd:
        from kapsel.core.block.registry import get_block_registry
        latest = get_block_registry().latest()
        if latest:
            target_cmd = latest.command
        else:
            con.print("[yellow]Please specify a command to explain.[/] Usage: kps ai explain <command>\n")
            return 1

    con.print(f"\n[bold #00f0ff]🔍 正在剖析指令:[/] [bold white]{target_cmd}[/]")

    sys_prompt = f"""You are Kapsel Command Explainer for {ctx['shell']} on {ctx['os']}.
Break down the provided command step by step.
Explain what the command does as a whole, then dissect each argument, flag, and pipe in clear bullet points.
Keep explanations concise, precise, and practical for developers.
"""

    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": f"Command: {target_cmd}"},
    ]

    try:
        con.print()
        client.chat_completion(messages, temperature=0.1, stream=True, console=con)
        con.print("\n")
        return 0
    except Exception as e:
        con.print(f"[bold #f43f5e]AI Error:[/] {e}\n")
        return 1


def action_pipe(prompt: str, pipe_content: str, con: Console, client: AiClient) -> int:
    """Processes piped stdin data with an AI prompt."""
    con.print(f"[dim]Processing piped data ({len(pipe_content)} chars)...[/]\n")

    sys_prompt = """You are a terminal stream data processor.
Analyze the piped terminal output according to the user's prompt.
Extract, summarize, or filter the information cleanly without conversational filler.
"""

    user_msg = f"""=== PIPED TERMINAL DATA ===
{pipe_content[:8000]}
===========================

Instruction: {prompt or 'Summarize and extract key insights or anomalies from this output.'}
"""

    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": user_msg},
    ]

    try:
        client.chat_completion(messages, temperature=0.1, stream=True, console=con)
        con.print("\n")
        return 0
    except Exception as e:
        con.print(f"[bold #f43f5e]AI Error:[/] {e}\n")
        return 1


def action_scout(con: Console, client: AiClient) -> int:
    """Inspects workspace manifests and briefs the developer on architecture and commands."""
    cwd = Path.cwd()
    con.print(f"\n[bold #00f0ff]🔭 Kapsel Project Scout (Scanning {cwd.name})...[/]")

    # Gather manifest snippets
    files = [f.name for f in cwd.iterdir() if not f.name.startswith(".")][:35]
    manifests: Dict[str, str] = {}

    interesting = [
        "package.json", "Cargo.toml", "pyproject.toml", "go.mod", "Makefile",
        "Dockerfile", "docker-compose.yml", "pom.xml", "requirements.txt",
    ]

    for m in interesting:
        p = cwd / m
        if p.is_file():
            try:
                manifests[m] = p.read_text(encoding="utf-8", errors="ignore")[:2500]
            except Exception:
                pass

    if not manifests and not files:
        con.print("[yellow]Empty directory. Nothing to scout.[/]\n")
        return 0

    manifest_summary = "\n\n".join(f"--- {name} ---\n{content}" for name, content in manifests.items())

    sys_prompt = """You are Kapsel Project Scout.
Brief the developer on this workspace:
1. Tech Stack & Framework (Primary languages, runtime, libraries)
2. How to Run, Build, and Test (Exact CLI commands based on package scripts or manifests)
3. Project Architecture & Entrypoints
Keep it crisp, organized into clear bullet points, under 10 items total.
"""

    user_msg = f"""Files in root:
{', '.join(files)}

Manifest Contents:
{manifest_summary or '(No standard package manifests found)'}
"""

    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": user_msg},
    ]

    try:
        con.print()
        client.chat_completion(messages, temperature=0.1, stream=True, console=con)
        con.print("\n")
        return 0
    except Exception as e:
        con.print(f"[bold #f43f5e]AI Error:[/] {e}\n")
        return 1
