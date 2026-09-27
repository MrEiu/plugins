"""
Terminal Tab Bar component for Kapsel TUI.
Provides multi-tab session management and visual tab indicators with status dots.
All comments and docstrings are in English.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional

from rich.text import Text
from textual.message import Message
from textual.widgets import Static


@dataclass
class TerminalTabItem:
    """Metadata for an open terminal session tab."""
    id: str
    title: str
    dot_color: str = "#10b981"  # Green
    active: bool = False


class TerminalTabBar(Static):
    """Top tab bar widget rendering multi-terminal tabs."""

    class TabSwitchRequested(Message):
        """Emitted when a tab switch is requested."""
        def __init__(self, tab_index: int) -> None:
            super().__init__()
            self.tab_index = tab_index

    class NewTabRequested(Message):
        """Emitted when a new tab is requested."""
        pass

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.id = "tab-bar-container"
        self.tabs: List[TerminalTabItem] = [
            TerminalTabItem(id="tab-1", title="pwsh", dot_color="#10b981", active=True)
        ]
        self.active_index: int = 0

    def add_tab(self, title: str = "shell") -> int:
        """Adds a new tab and activates it."""
        for t in self.tabs:
            t.active = False

        colors = ["#10b981", "#f59e0b", "#a855f7", "#38bdf8", "#ec4899"]
        color = colors[len(self.tabs) % len(colors)]
        new_tab = TerminalTabItem(
            id=f"tab-{len(self.tabs) + 1}",
            title=title,
            dot_color=color,
            active=True,
        )
        self.tabs.append(new_tab)
        self.active_index = len(self.tabs) - 1
        self.refresh()
        return self.active_index

    def close_current_tab(self) -> Optional[int]:
        """Closes currently active tab if more than one tab exists."""
        if len(self.tabs) <= 1:
            return None

        del self.tabs[self.active_index]
        self.active_index = max(0, min(self.active_index, len(self.tabs) - 1))
        self.tabs[self.active_index].active = True
        self.refresh()
        return self.active_index

    def select_tab(self, index: int) -> bool:
        """Selects tab by 0-based index."""
        if 0 <= index < len(self.tabs):
            for i, t in enumerate(self.tabs):
                t.active = (i == index)
            self.active_index = index
            self.refresh()
            return True
        return False

    def render(self) -> Text:
        """Renders tab items with status dots and active underline highlights."""
        text = Text()

        for idx, tab in enumerate(self.tabs):
            dot = "● "
            if tab.active:
                text.append(" [ ", style="bold #38bdf8")
                text.append(dot, style=f"bold {tab.dot_color}")
                text.append(f"{idx + 1}: {tab.title}", style="bold #ffffff")
                text.append(" ] ", style="bold #38bdf8")
            else:
                text.append("   ", style="#8b949e")
                text.append(dot, style=tab.dot_color)
                text.append(f"{idx + 1}: {tab.title}", style="#8b949e")
                text.append("   ", style="#8b949e")

            text.append("│", style="#21262d")

        # Plus (+) button for adding tabs
        text.append("  [ + ]  ", style="dim #8b949e")

        return text
