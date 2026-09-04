"""
Kapsel Install Plugin package.
Bridges meta-package-manager to provide cross-platform package operations.
"""

from .plugin import InstallPlugin

# Standard entry point for Kapsel plugin loader
Plugin = InstallPlugin

__all__ = ["Plugin", "InstallPlugin"]
