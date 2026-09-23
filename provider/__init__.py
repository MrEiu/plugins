"""
Provider (AI Model & API Switcher) Plugin for Kapsel.
Bridges cc-switch (SaladDay/cc-switch-cli) to manage and switch AI coding assistant providers.
All comments and descriptions are in English.
"""

try:
    from .plugin import ProviderPlugin as Plugin
except ImportError:
    from plugins.provider.plugin import ProviderPlugin as Plugin

__all__ = ["Plugin"]
