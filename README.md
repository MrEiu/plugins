# Kapsel Plugins Collection

This repository houses the official and community plugins for the **Kapsel** terminal shell environment.

## Available Plugins

| Plugin | Description | Commands |
| :--- | :--- | :--- |
| [install](./install) | Unified cross-platform package manager powered by meta-package-manager (mpm). | kps install, kps update, kps search, kps sync -mpm |

## Installation

To enable a plugin into your Kapsel environment:

`ash
kapsel add <plugin_name>
# Example:
kapsel add install
`

## Structure

Each subdirectory is a standalone Kapsel plugin containing:
- plugin.py: The plugin implementation subclassing KapselPlugin.
- __init__.py: Package entry point exporting Plugin.
- pyproject.toml / README.md: Metadata and documentation.

## License
MIT License.
