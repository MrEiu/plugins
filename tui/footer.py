"""
Bottom Status Bar component for Kapsel TUI.
Renders shell metadata, terminal size, BlockRegistry state, and runtime environment.
All comments and docstrings are in English.
"""

from __future__ import annotations

import os
import sys
from typing import Optional

from rich.text import Text
from textual.widgets import Static

from kapsel.core.block.registry import get_block_registry
from kapsel.core.block.model import BlockStatus


class BottomStatusBar(Static):
    """Bottom status bar widget displaying active environment metrics and Kapsel state."""

    def __init__(self, shell_name: str = "pwsh", **kwargs):
        super().__init__(**kwargs)
        self.shell_name = shell_name
        self.id = "bottom-status-bar"
        self._term_size: str = "120x35"

    def update_size(self, cols: int, rows: int) -> None:
        """Updates the displayed terminal dimension label."""
        self._term_size = f"{cols}x{rows}"
        self.refresh()

    def render(self) -> Text:
        text = Text()

        # Left segment
        text.append(f"{self.shell_name} ", style="bold #38bdf8")
        text.append("│ ", style="#30363d")
        text.append("UTF-8 ", style="#8b949e")
        text.append("│ ", style="#30363d")
        text.append(f"{self._term_size} ", style="#8b949e")
        text.append("│ ", style="#30363d")

        # Block registry status
        try:
            reg = get_block_registry()
            running_cnt = sum(1 for b in reg.blocks if b.status == BlockStatus.RUNNING)
            if running_cnt > 0:
                text.append(f"blocks: {running_cnt} running ", style="bold #10b981")
            else:
                text.append("blocks: idle ", style="dim #8b949e")
        except Exception:
            text.append("blocks: idle ", style="dim #8b949e")

        text.append("│ ", style="#30363d")
        text.append("Tab: Focus ", style="#a855f7")

        # Right segment
        py_ver = f"python-{sys.version_info.major}.{sys.version_info.minor}"
        in_venv = ".venv" if (hasattr(sys, "real_prefix") or sys.base_prefix != sys.prefix) else "system"

        right_part = Text()
        right_part.append("capsel ", style="dim #8b949e")
        right_part.append(f"{py_ver} ", style="bold #e6edf3")
        right_part.append("│ ", style="#30363d")
        right_part.append(f"{in_venv} ", style="#a855f7" if in_venv == ".venv" else "#8b949e")
        right_part.append("│ ", style="#30363d")
        right_part.append("local", style="#10b981")

        # Calculate padding
        width = self.size.width or 80
        total_len = len(text.plain) + len(right_part.plain)
        pad = max(1, width - total_len - 2)
        text.append(" " * pad)
        text.append_text(right_part)

        return text
