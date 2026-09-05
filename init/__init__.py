"""
Init Plugin package entry point for Kapsel.
Exports the main InitPlugin class.
All comments and descriptions are in English.
"""

from .plugin import InitPlugin

# Plugin loader entry points
Plugin = InitPlugin
__all__ = ["InitPlugin", "Plugin"]
