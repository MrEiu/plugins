# Kapsel Plugin Template & Boilerplate Guide

Welcome to the canonical reference template for authoring **Kapsel Plugins**!

This directory provides a gold-standard boilerplate that follows all architectural conventions, lifecycle hooks, and best practices established across the Kapsel ecosystem.

---

## 📁 Plugin Anatomy

Every standard Kapsel plugin should be organized in its own directory under `plugins/<plugin_name>/`:

```text
plugins/<plugin_name>/
├── __init__.py          # Mandatory: Exports 'Plugin' and 'PluginClass'
├── plugin.py            # Core: PluginManifest, hooks, and kps command registration
├── engine.py            # Logic: Tool path resolution, subprocess execution, Rich rendering
├── install.py           # Dependency: External tool checker and installation guidance
└── README.md            # Docs: Usage instructions, flags, and installation steps
```

---

## 🔑 Crucial Architectural Rules

### 1. The `__init__.py` Export Rule (Critical!)
When Kapsel dynamically scans plugin directories, `PluginManager` imports `<plugin_dir>/__init__.py` and inspects it for a `Plugin` attribute subclassing `KapselPlugin`.

**Always include this in `__init__.py`:**
```python
from .plugin import Plugin, MyPlugin

__all__ = ["Plugin", "MyPlugin"]
```
*If `Plugin` is not exported from `__init__.py`, Kapsel will silently skip your plugin!*

---

### 2. Command Namespace Separation
- **`kps <name>`**: Reserved exclusively for invoking plugin tools (e.g., `kps template`, `kps shore`, `kps preview`).
- **`kapsel <subcommand>`**: Reserved exclusively for system administration and shell lifecycle (`status`, `config`, `enable`, `disable`, `upgrade`).
- **Zero Namespace Pollution**: Never hijack standard system CLI tools inside the `kps` namespace.

---

### 3. Safe Import Standards
Always use relative imports with fallback when importing sibling files within your plugin:
```python
try:
    from .engine import my_helper
except ImportError:
    from plugins.<plugin_name>.engine import my_helper
```
*This ensures your plugin works both when loaded dynamically from source and when installed as a standalone package.*

---

### 4. Code & Comment Language Standard
Per Kapsel guidelines, all source code comments, docstrings, and error messages in the codebase must remain in **English**.

---

## 🚀 How to Create a New Plugin from this Template

1. **Copy the directory**:
   ```bash
   cp -r plugins/template plugins/my_plugin
   ```

2. **Customize `PluginManifest` in `plugin.py`**:
   ```python
   manifest = PluginManifest(
       id="my_plugin",
       name="My Plugin",
       version="0.1.0",
       description="Short summary of what my plugin does.",
       author="Your Name",
       homepage="https://github.com/...",
       min_kapsel_version="0.1.0",
       tags=["tool", "utility"],
   )
   ```

3. **Implement your core logic in `engine.py`**:
   - Tool executable discovery via `resolve_tool_executable()`.
   - Subprocess execution or API calls.
   - Rich panel / table output formatting.

4. **Enable your plugin in Kapsel**:
   ```bash
   kapsel enable my_plugin
   ```

5. **Test your commands**:
   ```bash
   kps my_plugin info
   ```

---

## 🪝 Lifecycle Hooks Reference

| Hook | Purpose | Example |
| :--- | :--- | :--- |
| **`HookType.FILTER_COMMAND`** | Intercept or rewrite commands before execution | Intercepting shortcuts (e.g. `tmpl <arg>`) or streaming pipelines (`<cmd> \| tr`) |
| **`HookType.PROVIDE_COMPLETIONS`** | Provide dynamic tab completion candidates | Auto-suggesting subcommands, flags, or language tags |
| **`context.register_kps_command`** | Register official command under `kps` | Exposing `kps my_plugin` with help text, usage, and argument dispatching |
