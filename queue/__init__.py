"""
Queue Plugin for Kapsel.
Bridges Pueue to provide autonomous background task queuing, daemon management, and live logging.
All comments and descriptions are in English.
"""

from .plugin import QueuePlugin, AutopilotPlugin

Plugin = QueuePlugin

__all__ = ["QueuePlugin", "AutopilotPlugin", "Plugin"]
