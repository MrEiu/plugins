"""
TUI (Full-Screen Developer Workbench) Plugin for Kapsel.

Provides an aesthetic, Web-grade full-screen TUI workbench:
1. Left: Permanent interactive workspace file tree.
2. Right: Native multi-tab PTY terminal powered by pyte and winpty/ptyprocess.
3. Universal 'Tab' leader key for instant pane navigation.

All comments and docstrings are in English.
"""

from .plugin import TuiPlugin

Plugin = TuiPlugin

__all__ = ["TuiPlugin", "Plugin"]
