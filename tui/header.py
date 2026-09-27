"""
Top Header Bar component for Kapsel TUI.
Renders branding, active Git branch, and CWD breadcrumbs.
All comments and docstrings are in English.
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
from typing import Optional

from rich.text import Text
from textual.widgets import Static


def _get_active_git_branch(cwd: Optional[Path] = None) -> Optional[str]:
    """Detects active git branch if cwd is within a git repository."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(cwd or Path.cwd()),
            capture_output=True,
            text=True,
            check=False,
            timeout=0.3,
        )
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except Exception:
        pass
    return None


class TopHeader(Static):
    """Top header widget displaying Kapsel brand, workspace branch, and CWD."""

    def __init__(self, workspace_path: Optional[Path] = None, **kwargs):
        super().__init__(**kwargs)
        self.workspace_path = workspace_path or Path.cwd()
        self.id = "top-header"

    def render(self) -> Text:
        text = Text()

        # 1. Brand icon & name
        text.append("● ", style="bold #00f0ff")
        text.append("KAPSEL", style="bold #ffffff")
        text.append("   │  ", style="#30363d")

        # 2. Workspace & Git Branch
        branch = _get_active_git_branch(self.workspace_path)
        branch_str = branch or "main"
        text.append("🟢 ", style="#10b981")
        text.append(f"workspace / {branch_str}", style="bold #e6edf3")

        # 3. Spacing to right align
        text.append("   │  ", style="#30363d")
        cwd_str = str(self.workspace_path)
        text.append(cwd_str, style="dim #8b949e")

        # Right icon badges
        text.append("  ⚙ ⚡ 🗖", style="#7d8590")

        return text
