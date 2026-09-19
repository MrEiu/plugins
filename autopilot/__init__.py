"""
Autopilot (PM2 Process Manager) Plugin for Kapsel.
Production process manager, cluster supervisor, and daemon orchestrator powered by PM2.
All comments and descriptions are in English.
"""

from .plugin import AutopilotPlugin

Plugin = AutopilotPlugin

__all__ = ["AutopilotPlugin", "Plugin"]
