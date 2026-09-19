"""
Commit Plugin Engine: Offline rule-based Conventional Commit deduction and interactive workflow.
All comments and docstrings are in English.
"""

from collections import Counter
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

try:
    from prompt_toolkit import prompt as pt_prompt
    from prompt_toolkit.application import Application
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout import Layout, Window
    from prompt_toolkit.layout.controls import FormattedTextControl
    from prompt_toolkit.styles import Style
    from kapsel.ui.prompt import get_safe_output
except ImportError:
    get_safe_output = lambda: None

COMMIT_TYPES = [
    ("feat", "A new feature or capability", "🚀"),
    ("fix", "A bug fix or error correction", "🐛"),
    ("docs", "Documentation only changes", "📝"),
    ("refactor", "Code change that neither fixes a bug nor adds a feature", "♻️"),
    ("perf", "A code change that improves performance", "⚡"),
    ("test", "Adding missing tests or correcting existing tests", "🧪"),
    ("style", "Changes that do not affect the meaning of the code", "🎨"),
    ("chore", "Build process, dependencies, or auxiliary tool changes", "🔧"),
]

PICKER_STYLE = Style.from_dict({
    "commit.header": "bold #00f0ff",
    "commit.cursor": "bold #10b981",
    "commit.item_selected": "bold #ffffff bg:#334155",
    "commit.item_unselected": "#cbd5e1",
    "commit.type": "bold #38bdf8",
    "commit.desc": "dim #94a3b8",
    "commit.footer": "dim #94a3b8",
    "commit.footer_key": "bold #38bdf8",
})


def is_git_repository(cwd: Optional[Path] = None) -> bool:
    """Checks whether the given directory (or CWD) is inside a Git repository."""
    if not shutil.which("git"):
        return False
    target = cwd or Path.cwd()
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=str(target),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return res.returncode == 0 and res.stdout.strip() == "true"
    except Exception:
        return False


def get_git_status_files(cwd: Optional[Path] = None) -> List[Dict[str, Any]]:
    """
    Parses 'git status --porcelain -uall' to extract modified, added, deleted,
    and untracked files with their staging state.
    """
    target = cwd or Path.cwd()
    try:
        res = subprocess.run(
            ["git", "status", "--porcelain", "-uall"],
            cwd=str(target),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if res.returncode != 0 or not res.stdout.strip():
            return []

        files: List[Dict[str, Any]] = []
        for line in res.stdout.splitlines():
            line_str = line.strip()
            if not line_str or len(line) < 3:
                continue

            index_status = line[0]
            worktree_status = line[1]
            raw_path = line[3:].strip().strip("\"'")

            # Handle rename format: "old -> new"
            if " -> " in raw_path:
                raw_path = raw_path.split(" -> ")[1].strip()

            is_staged = index_status not in (" ", "?")
            status_code = index_status if index_status != " " else worktree_status

            files.append({
                "path": raw_path,
                "status": status_code,
                "is_staged": is_staged,
                "raw_line": line,
            })
        return files
    except Exception:
        return []


def get_current_git_branch(cwd: Optional[Path] = None) -> str:
    """Returns the name of the current Git branch, or empty string."""
    target = cwd or Path.cwd()
    try:
        res = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=str(target),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if res.returncode == 0:
            return res.stdout.strip()
    except Exception:
        pass
    return ""


def deduce_scope(files: List[Dict[str, Any]]) -> str:
    """
    Analyzes changed file paths to infer the most accurate architectural scope.
    Examples:
    - 'plugins/portal/plugin.py' -> 'portal'
    - 'kapsel/ui/prompt.py' -> 'ui'
    - 'tests/test_plugin_preview.py' -> 'preview'
    """
    if not files:
        return ""

    candidates: List[str] = []

    for f in files:
        p = Path(f["path"])
        parts = p.parts
        if not parts:
            continue

        # Rule 1: plugins/<name>/...
        if len(parts) >= 2 and parts[0] == "plugins":
            candidates.append(parts[1])
            continue

        # Rule 2: tests/test_plugin_<name>.py or tests/test_<name>.py
        if parts[0] == "tests" and p.name.startswith("test_"):
            clean_name = p.stem.replace("test_plugin_", "").replace("test_", "")
            candidates.append(clean_name)
            continue

        # Rule 3: kapsel/<module>/...
        if len(parts) >= 2 and parts[0] == "kapsel":
            candidates.append(parts[1])
            continue

        # Rule 4: docs/... or doc files
        if parts[0] in ("docs", "doc") or p.suffix.lower() in (".md", ".rst"):
            candidates.append("docs")
            continue

        # Top-level directory
        if len(parts) > 1:
            candidates.append(parts[0])

    if not candidates:
        return ""

    # Pick the most frequently occurring scope candidate
    counter = Counter(candidates)
    most_common, count = counter.most_common(1)[0]
    return most_common


def deduce_type_and_subject(
    files: List[Dict[str, Any]],
    scope: str,
    branch_name: str = "",
) -> Tuple[str, str]:
    """
    Deduces the Conventional Commit type and high-level human-readable description
    from file paths, extensions, git statuses, and active branch context.
    """
    if not files:
        return "chore", "update repository"

    paths = [f["path"].lower() for f in files]
    statuses = [f["status"] for f in files]

    # Check branch context (e.g. feat/login, fix/overflow)
    branch_lower = branch_name.lower()
    branch_type = None
    if "/" in branch_lower:
        prefix = branch_lower.split("/")[0]
        if prefix in ("feat", "fix", "docs", "refactor", "perf", "test", "chore", "style"):
            branch_type = prefix

    # 1. Documentation rule
    if all(p.endswith((".md", ".rst", ".txt")) or "docs/" in p or p == "license" for p in paths):
        if len(files) == 1 and files[0]["path"].lower().endswith("readme.md"):
            return "docs", "update README documentation"
        return "docs", f"update {scope or 'project'} documentation"

    # 2. Test rule
    if all(p.startswith("tests/") or "test" in Path(p).name for p in paths):
        if scope and scope != "tests":
            return "test", f"add and update test assertions for {scope}"
        return "test", "update test suite and test coverage"

    # 3. Build & Configuration rule
    config_names = ("pyproject.toml", "package.json", "cargo.toml", "requirements.txt", "catalog.json", ".gitignore")
    if all(any(p.endswith(cfg) for cfg in config_names) or p.startswith(".github/") for p in paths):
        if any("catalog.json" in p for p in paths):
            return "chore", f"bump version and update {scope or 'plugin'} catalog"
        return "chore", f"update dependencies and configuration for {scope or 'project'}"

    # 4. Performance rule
    if any("bench" in p or "perf" in p for p in paths):
        return "perf", f"optimize performance in {scope or 'core engine'}"

    # 5. Bug fix rule
    if branch_type == "fix" or any(kw in branch_lower for kw in ("fix", "bug", "patch", "hotfix", "issue")):
        return "fix", f"resolve issue and refine {scope or 'component'} logic"

    # 6. Feature addition rule (new files added)
    has_new_files = any(s in ("A", "?") for s in statuses)
    if branch_type == "feat" or has_new_files:
        if len(files) == 1:
            name = Path(files[0]["path"]).stem
            return "feat", f"implement {name} functionality"
        return "feat", f"implement {scope or 'feature'} and enhance capabilities"

    # 7. Refactoring rule (clean modifications to existing code)
    if branch_type == "refactor" or all(s == "M" for s in statuses):
        if len(files) == 1:
            name = Path(files[0]["path"]).stem
            return "refactor", f"refine and streamline {name} implementation"
        return "refactor", f"refactor {scope or 'core'} implementation and clean up codebase"

    # Fallback
    chosen_type = branch_type or "feat"
    return chosen_type, f"update {scope or 'codebase'} implementation"


def deduce_commit_message(cwd: Optional[Path] = None) -> Tuple[str, List[Dict[str, Any]], Dict[str, str]]:
    """
    End-to-end deduction: reads git status, derives scope, type, and subject,
    and returns formatted Conventional Commit message with metadata.
    """
    files = get_git_status_files(cwd)
    if not files:
        return "", [], {"type": "", "scope": "", "subject": ""}

    branch = get_current_git_branch(cwd)
    scope = deduce_scope(files)
    commit_type, subject = deduce_type_and_subject(files, scope, branch)

    # Format conventional commit: type(scope): subject
    if scope:
        full_message = f"{commit_type}({scope}): {subject}"
    else:
        full_message = f"{commit_type}: {subject}"

    meta = {
        "type": commit_type,
        "scope": scope,
        "subject": subject,
        "branch": branch,
    }
    return full_message, files, meta


def select_commit_type_interactive(initial_type: str = "feat") -> str:
    """
    Presents an interactive prompt_toolkit arrow-key menu to switch commit type.
    Keys: [Up/Down] to navigate, [Enter] to select, [Esc] to cancel.
    """
    if not sys.stdin.isatty():
        return initial_type

    selected_idx = 0
    for idx, (t, _, _) in enumerate(COMMIT_TYPES):
        if t == initial_type:
            selected_idx = idx
            break

    def get_tokens() -> List[Tuple[str, str]]:
        tokens: List[Tuple[str, str]] = [
            ("class:commit.header", "\n🎯 Select Conventional Commit Type:\n"),
        ]
        for idx, (c_type, desc, icon) in enumerate(COMMIT_TYPES):
            is_selected = (idx == selected_idx)
            pad = " " * max(1, 10 - len(c_type))
            if is_selected:
                tokens.append(("class:commit.cursor", " ❯ "))
                tokens.append(("class:commit.item_selected", f" {icon} {c_type}{pad}"))
                tokens.append(("class:commit.desc", f" {desc}\n"))
            else:
                tokens.append(("", "   "))
                tokens.append(("class:commit.type", f" {icon} {c_type}{pad}"))
                tokens.append(("class:commit.desc", f" {desc}\n"))

        tokens.extend([
            ("class:commit.footer", "\n "),
            ("class:commit.footer_key", "[↑/↓]"),
            ("class:commit.footer", " Select · "),
            ("class:commit.footer_key", "[Enter]"),
            ("class:commit.footer", " Confirm · "),
            ("class:commit.footer_key", "[Esc]"),
            ("class:commit.footer", " Keep Current\n"),
        ])
        return tokens

    kb = KeyBindings()

    @kb.add("up")
    def _up(event: Any) -> None:
        nonlocal selected_idx
        selected_idx = (selected_idx - 1) % len(COMMIT_TYPES)
        event.app.invalidate()

    @kb.add("down")
    def _down(event: Any) -> None:
        nonlocal selected_idx
        selected_idx = (selected_idx + 1) % len(COMMIT_TYPES)
        event.app.invalidate()

    @kb.add("enter")
    def _enter(event: Any) -> None:
        event.app.exit(result=COMMIT_TYPES[selected_idx][0])

    @kb.add("escape")
    @kb.add("c-c")
    def _cancel(event: Any) -> None:
        event.app.exit(result=initial_type)

    try:
        app = Application(
            layout=Layout(Window(FormattedTextControl(get_tokens))),
            key_bindings=kb,
            style=PICKER_STYLE,
            full_screen=False,
            output=get_safe_output(),
        )
        return app.run() or initial_type
    except Exception:
        return initial_type


def copy_to_clipboard(text: str) -> bool:
    """Copies text to clipboard cross-platform."""
    try:
        if sys.platform == "win32":
            subprocess.run(["clip"], input=text.encode("utf-16le"), check=True)
            return True
        elif sys.platform == "darwin":
            subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True)
            return True
        else:
            for tool in ["wl-copy", "xclip", "xsel"]:
                if shutil.which(tool):
                    cmd = [tool, "-selection", "clipboard"] if tool == "xclip" else [tool]
                    subprocess.run(cmd, input=text.encode("utf-8"), check=True)
                    return True
    except Exception:
        pass
    return False


def execute_git_commit(
    message: str,
    stage_all: bool = True,
    con: Optional[Console] = None,
    cwd: Optional[Path] = None,
) -> int:
    """
    Executes 'git add -A' (if stage_all is True) and 'git commit -m "<message>"'.
    Returns the command returncode.
    """
    c = con or Console(legacy_windows=False)
    target = cwd or Path.cwd()

    if stage_all:
        try:
            subprocess.run(
                ["git", "add", "-A"],
                cwd=str(target),
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as e:
            c.print(f"[bold #f43f5e]Git add failed:[/] {e}\n")
            return 1

    try:
        proc = subprocess.run(
            ["git", "commit", "-m", message],
            cwd=str(target),
        )
        if proc.returncode == 0:
            c.print(f"\n[bold #10b981]✔ Successfully committed changes![/]")
            c.print(f"[dim]Commit message:[/] [white]{message}[/]\n")
        return proc.returncode
    except Exception as e:
        c.print(f"[bold #f43f5e]Git commit failed:[/] {e}\n")
        return 1
