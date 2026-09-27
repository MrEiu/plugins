"""
Workspace File Tree component for Kapsel TUI.
Provides interactive directory hierarchy with icons, expand/collapse, and path injection.
All comments and docstrings are in English.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, Optional, Set

from rich.text import Text
from textual.message import Message
from textual.widgets import Tree


# Directories and files to ignore in workspace tree
IGNORED_PATTERNS: Set[str] = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".gemini",
    ".idea",
    ".vscode",
    ".DS_Store",
}


def _get_file_icon(path: Path) -> tuple[str, str]:
    """Returns (icon, color_style) for a given file or directory."""
    if path.is_dir():
        return ("📁 ", "bold #38bdf8")

    ext = path.suffix.lower()
    name = path.name.lower()

    if ext in (".py", ".pyw"):
        return ("π ", "bold #10b981")
    elif ext in (".json", ".toml", ".yaml", ".yml", ".ini"):
        return ("◇ ", "#f59e0b")
    elif ext in (".md", ".txt", ".rst"):
        return ("# ", "#a855f7")
    elif ext in (".sh", ".ps1", ".bat", ".cmd"):
        return ("⚡ ", "#ef4444")
    elif ext in (".rs", ".go", ".c", ".cpp", ".h", ".ts", ".js"):
        return ("λ ", "#06b6d4")
    else:
        return ("📄 ", "#8b949e")


class WorkspaceTree(Tree[Path]):
    """Interactive workspace file tree widget with keyboard navigation and path selection."""

    class FileSelected(Message):
        """Emitted when a file is selected with Enter or double-click."""
        def __init__(self, path: Path) -> None:
            super().__init__()
            self.path = path

    def __init__(self, root_path: Optional[Path] = None, **kwargs):
        self.root_path = root_path or Path.cwd()
        super().__init__(label=self.root_path.name or "Workspace", data=self.root_path, **kwargs)
        self.show_root = False
        self.guide_depth = 2

    def on_mount(self) -> None:
        """Populates the initial directory tree upon mounting."""
        self.load_directory(self.root, self.root_path)

    def load_directory(self, node, path: Path, max_depth: int = 2, current_depth: int = 0) -> None:
        """Populates child nodes for a directory."""
        if current_depth > max_depth:
            return

        try:
            entries = sorted(
                list(path.iterdir()),
                key=lambda p: (not p.is_dir(), p.name.lower())
            )
        except (PermissionError, OSError):
            return

        for entry in entries:
            if entry.name in IGNORED_PATTERNS or entry.name.startswith("."):
                continue

            icon, style = _get_file_icon(entry)
            label = Text()
            label.append(icon, style=style)
            label.append(entry.name, style="#e6edf3" if entry.is_dir() else "#c9d1d9")

            if entry.is_dir():
                child_node = node.add(label, data=entry, expand=current_depth < 1)
                self.load_directory(child_node, entry, max_depth=max_depth, current_depth=current_depth + 1)
            else:
                node.add_leaf(label, data=entry)

    def on_tree_node_selected(self, event: Tree.NodeSelected[Path]) -> None:
        """Handles node selection (Enter / click)."""
        target_path = event.node.data
        if target_path and target_path.is_file():
            self.post_message(self.FileSelected(target_path))
