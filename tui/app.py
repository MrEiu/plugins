"""
Main Textual Application for Kapsel TUI Workbench.
Coordinates layouts, Leader-key state machine, FileTree, and multi-tab Terminal engine.
All comments and docstrings are in English.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys
import time
from typing import Dict, List, Optional

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.events import Key
from textual.widgets import Static

from .footer import BottomStatusBar
from .header import TopHeader
from .tabs import TerminalTabBar
from .terminal import TerminalWidget
from .tree import WorkspaceTree


class KapselWorkbenchApp(App):
    """
    Main Kapsel TUI Workbench Application.
    Full-screen developer workbench with permanent left file tree and right native PTY terminal.
    """

    CSS_PATH = "styles.tcss"

    def __init__(self, workspace_path: Optional[Path] = None, **kwargs):
        super().__init__(**kwargs)
        self.workspace_path = workspace_path or Path.cwd()
        self.tree_widget: Optional[WorkspaceTree] = None
        self.tab_bar: Optional[TerminalTabBar] = None
        self.header_bar: Optional[TopHeader] = None
        self.status_bar: Optional[BottomStatusBar] = None
        self.leader_bar: Optional[Static] = None

        # Terminal instances mapped by tab index
        self.terminals: List[TerminalWidget] = []
        self.active_terminal_index: int = 0
        self.term_container: Optional[Vertical] = None

        # Tab Leader state machine
        self._leader_active: bool = False
        self._leader_time: float = 0.0

    def compose(self) -> ComposeResult:
        """Composes the full-screen layout structure."""
        self.header_bar = TopHeader(workspace_path=self.workspace_path)
        yield self.header_bar

        with Horizontal(id="main-split"):
            with Vertical(id="file-tree-container"):
                yield Static("FILES  Kapsel", id="file-tree-header")
                self.tree_widget = WorkspaceTree(root_path=self.workspace_path)
                yield self.tree_widget

            with Vertical(id="terminal-workspace") as term_ws:
                self.term_container = term_ws
                self.tab_bar = TerminalTabBar()
                yield self.tab_bar

                # Initial default terminal widget
                initial_term = TerminalWidget(cwd=self.workspace_path)
                self.terminals.append(initial_term)
                yield initial_term

        self.status_bar = BottomStatusBar()
        yield self.status_bar

        self.leader_bar = Static(
            "⚡ TAB LEADER MODE: [T] New Tab │ [W] Close │ [B] Sidebar │ [1-9] Switch │ [Q] Quit",
            id="leader-indicator",
        )
        yield self.leader_bar

    def on_mount(self) -> None:
        """Focuses the terminal upon mounting."""
        if self.terminals:
            self.terminals[0].focus()

    def action_toggle_focus(self) -> None:
        """Toggles focus between Left FileTree and Right Terminal."""
        active_term = self._get_active_terminal()
        if self.tree_widget and self.tree_widget.has_focus:
            if active_term:
                active_term.focus()
        elif self.tree_widget:
            self.tree_widget.focus()

    def _get_active_terminal(self) -> Optional[TerminalWidget]:
        """Returns currently active TerminalWidget instance."""
        if 0 <= self.active_terminal_index < len(self.terminals):
            return self.terminals[self.active_terminal_index]
        return None

    def action_new_tab(self) -> None:
        """Creates a new terminal tab and mounts a new PTY session."""
        if not self.tab_bar or not self.term_container:
            return

        new_idx = self.tab_bar.add_tab(title=f"pwsh-{len(self.terminals) + 1}")
        new_term = TerminalWidget(cwd=self.workspace_path)
        self.terminals.append(new_term)

        # Hide current terminal and mount new one
        for t in self.terminals[:-1]:
            t.display = False

        self.term_container.mount(new_term)
        self.active_terminal_index = new_idx
        new_term.focus()

    def action_close_tab(self) -> None:
        """Closes currently active terminal tab and terminates its PTY."""
        if len(self.terminals) <= 1:
            return

        closing_term = self.terminals[self.active_terminal_index]
        closing_term.terminate()
        closing_term.remove()
        del self.terminals[self.active_terminal_index]

        new_idx = self.tab_bar.close_current_tab() if self.tab_bar else 0
        self.active_terminal_index = new_idx or 0

        # Activate remaining terminal
        active_term = self._get_active_terminal()
        if active_term:
            active_term.display = True
            active_term.focus()

    def action_switch_tab(self, index: int) -> None:
        """Switches visible terminal to the specified index."""
        if not self.tab_bar:
            return

        if self.tab_bar.select_tab(index):
            self.active_terminal_index = index
            for i, term in enumerate(self.terminals):
                term.display = (i == index)
            active_term = self._get_active_terminal()
            if active_term:
                active_term.focus()

    def action_toggle_sidebar(self) -> None:
        """Toggles visibility of the left file tree sidebar."""
        sidebar = self.query_one("#file-tree-container")
        if sidebar:
            sidebar.display = not sidebar.display
            if not sidebar.display:
                active_term = self._get_active_terminal()
                if active_term:
                    active_term.focus()

    def on_workspace_tree_file_selected(self, message: WorkspaceTree.FileSelected) -> None:
        """Injects selected file path into active terminal prompt."""
        active_term = self._get_active_terminal()
        if active_term:
            try:
                rel_path = message.path.relative_to(self.workspace_path)
                path_str = str(rel_path)
            except ValueError:
                path_str = str(message.path)

            if " " in path_str:
                path_str = f'"{path_str}"'

            active_term.write_input(f"{path_str} ")
            active_term.focus()

    def on_key(self, event: Key) -> None:
        """
        Global Key Handler implementing the Tab Leader Key state machine.
        - Single Tab: Focus toggle between tree and terminal
        - Tab + T: New Tab
        - Tab + W: Close Tab
        - Tab + B: Toggle Sidebar
        - Tab + 1..9: Jump to Tab
        - Tab + Q: Quit
        """
        key_name = event.key.lower()

        # Handle Leader Chords
        if self._leader_active:
            self._leader_active = False
            if self.leader_bar:
                self.leader_bar.remove_class("visible")

            if key_name == "t":
                self.action_new_tab()
                event.stop()
                return
            elif key_name == "w":
                self.action_close_tab()
                event.stop()
                return
            elif key_name == "b":
                self.action_toggle_sidebar()
                event.stop()
                return
            elif key_name in ("1", "2", "3", "4", "5", "6", "7", "8", "9"):
                idx = int(key_name) - 1
                self.action_switch_tab(idx)
                event.stop()
                return
            elif key_name == "q":
                self.exit()
                event.stop()
                return
            elif key_name == "tab":
                # Double Tab pressed: toggle focus
                self.action_toggle_focus()
                event.stop()
                return

        # Direct shortcuts
        if key_name == "tab":
            # Activate Tab leader mode
            self._leader_active = True
            self._leader_time = time.time()
            if self.leader_bar:
                self.leader_bar.add_class("visible")

            # Schedule a single-tab focus toggle fallback if no chord follows
            self.set_timer(0.35, self._check_single_tab_fallback)
            event.stop()
            return
        elif key_name == "ctrl+t":
            self.action_new_tab()
            event.stop()
        elif key_name == "ctrl+w":
            self.action_close_tab()
            event.stop()
        elif key_name == "ctrl+b":
            self.action_toggle_sidebar()
            event.stop()
        elif key_name == "ctrl+q":
            self.exit()
            event.stop()

    def _check_single_tab_fallback(self) -> None:
        """If leader key timed out without chord keys, execute simple focus toggle."""
        if self._leader_active and (time.time() - self._leader_time) >= 0.3:
            self._leader_active = False
            if self.leader_bar:
                self.leader_bar.remove_class("visible")
            self.action_toggle_focus()

    def on_unmount(self) -> None:
        """Clean shutdown of all PTY background processes."""
        for term in self.terminals:
            try:
                term.terminate()
            except Exception:
                pass
