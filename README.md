# 🔌 Kapsel Plugins

**The official plugin ecosystem for Kapsel.**

This repository contains the official Kapsel plugins and provides the
development, packaging, installation, and contribution conventions used by
the ecosystem.

Kapsel plugins are intentionally decoupled from the core runtime. A plugin
can provide commands, integrations, workflows, completion specifications,
and external developer tools without expanding the Kapsel core itself.

> **Core principle:** Kapsel provides the capsule; plugins provide the
> capabilities.

---

## 🌐 Plugin Ecosystem

The repository is the home of the official plugin collection, but the
architecture is designed for community contributions as well.

```text
                         Kapsel
                           │
                    ┌──────┴──────┐
                    │             │
                 Core        Plugin Ecosystem
                                  │
                         ┌────────┴────────┐
                         │                 │
                     Official          Community
                     Plugins            Plugins
```

### Official Plugins

Official plugins are maintained as part of the Kapsel ecosystem and follow
the conventions defined in this repository.

### Community Plugins

Third-party developers are welcome to create and submit plugins.

Community plugins should follow the same plugin interface, packaging rules,
installation conventions, and platform compatibility requirements described
below.

For contribution and submission details, see
[Plugin Contribution](#-plugin-contribution).

---

# 📁 Repository Structure

Each plugin is maintained as an independent package under the `plugins/`
directory:

```text
plugins/
├── <plugin_name>/
│   ├── __init__.py
│   ├── plugin.py
│   ├── install.py
│   ├── pyproject.toml
│   ├── README.md
│   └── LICENSE
│
└── ...
```

### Plugin Files

| File | Purpose |
| :--- | :--- |
| `__init__.py` | Exposes the plugin entry point |
| `plugin.py` | Core plugin logic, commands, and lifecycle hooks |
| `install.py` | Optional installation logic for external dependencies |
| `pyproject.toml` | Package metadata and Python dependencies |
| `README.md` | Complete plugin documentation and usage examples |
| `LICENSE` | Plugin license |

A plugin should remain as self-contained as practical. Installation logic,
runtime logic, metadata, and documentation should live with the plugin rather
than being scattered across the repository.

---

# 🧩 Plugin Interface

A plugin is loaded by Kapsel through its plugin entry point.

The plugin implementation should inherit from the Kapsel plugin base and
register its commands and lifecycle hooks through the supported API.

A minimal structure looks like:

```python
from kapsel.plugin import KapselPlugin


class MyPlugin(KapselPlugin):
    name = "myplugin"

    def register(self):
        ...
```

The exact API may evolve with the Kapsel core. Plugin implementations should
use the public plugin interfaces rather than depending on internal Kapsel
modules.

---

# 📦 External Dependencies

Plugins may depend on external command-line tools.

The installation strategy is intentionally standardized so that plugins do
not create isolated, ad-hoc environments on a user's machine.

## Installation Principles

### 1. Prefer `kps install`

When the required tool is available through Kapsel's unified installation
layer, prefer:

```bash
kps install <tool>
```

This allows Kapsel to select an appropriate system package manager for the
host platform.

### 2. Install Required Package Managers First

Some CLI tools are distributed through a dedicated package manager.

For example, a Python CLI may require `pipx`, while a Rust CLI may require
`cargo`.

If the required package manager is missing:

```text
Package Manager
      ↓
Target Tool
```

Install the package manager first, then install the target tool through it.

Plugins should not create their own `venv`, temporary tool environments, or
private copies of system package managers unless the dependency explicitly
requires such behavior.

### 3. Respect the Host Platform

Installation logic must account for:

- Windows
- macOS
- Linux

A plugin should provide an appropriate installation path for each supported
platform and degrade gracefully when an optional installation mechanism is
unavailable.

---

# 🖥️ Cross-Platform Installation

The preferred installation order is:

| Platform | Preferred | Fallback | Final Fallback |
| :--- | :--- | :--- | :--- |
| **Windows** | `kps install` / Scoop / WinGet | Install required package manager first | Official prebuilt release |
| **macOS** | `kps install` / Homebrew | Install required package manager first | Official x86_64 / arm64 release |
| **Linux** | `kps install` / distro package manager / Homebrew | Install required package manager first | Official glibc / musl release |

The exact order may be adjusted when a tool has platform-specific
requirements.

The important rule is that the plugin should use the most native and
maintainable installation mechanism available before falling back to a
standalone binary.

---

# 🛠️ `install.py`

A plugin that requires external tools can provide an `install.py` module.

The installer should expose:

```python
def install(console: Console, bin_dir: Path) -> bool:
    ...
```

Its responsibilities are:

1. Detect whether the dependency is already installed.
2. Prefer `kps install` where appropriate.
3. Use the host platform's native package manager when appropriate.
4. Install a required package manager before installing its target tool.
5. Fall back to an official standalone release when available.
6. Return `True` only when the dependency is ready for use.

A minimal example:

```python
from pathlib import Path
import platform
import shutil
import subprocess
import sys

from rich.console import Console


def install(console: Console, bin_dir: Path) -> bool:
    tool_name = "<tool_name>"

    if shutil.which(tool_name):
        console.print(f"[dim]✔ {tool_name} is already installed.[/]")
        return True

    system = platform.system().lower()

    # 1. Prefer Kapsel's unified installer.
    if shutil.which("kps"):
        result = subprocess.run(
            ["kps", "install", tool_name],
            stdout=subprocess.DEVNULL,
        )
        if result.returncode == 0 and shutil.which(tool_name):
            return True

    # 2. Add platform-specific installation logic here.
    #
    # Windows: Scoop / WinGet
    # macOS: Homebrew
    # Linux: apt / dnf / pacman / Homebrew
    #
    # 3. If the tool requires a package manager such as pipx,
    #    install that manager first and then install the target.

    console.print(
        f"[bold #f43f5e]✘ Automatic installation failed for {tool_name}.[/]"
    )
    return False
```

The example is intentionally minimal. Each plugin should implement only the
installation paths actually required by its dependencies.

---

# 🧹 Installation Hygiene

Plugins should avoid polluting the user's environment.

Do not:

- create arbitrary virtual environments for CLI dependencies;
- download tools into undocumented temporary directories;
- modify shell startup files directly;
- silently overwrite an existing system executable;
- assume a single package manager exists on every platform;
- embed platform-specific paths without detection.

Prefer:

```text
Kapsel / system package manager
          ↓
      target tool
```

over:

```text
Plugin
  ├── private venv
  ├── private package manager
  └── private copy of the tool
```

When a standalone binary is required, use the official upstream release when
possible and place Kapsel-managed binaries under the designated Kapsel
runtime directory.

---

# 📝 Plugin Documentation

Every plugin must include its own `README.md`.

A plugin README should explain:

```text
What does this plugin do?
How do I install it?
How do I use it?
What external dependencies does it require?
Which platforms are supported?
How do I configure it?
How do I contribute?
```

A typical structure is:

```markdown
# Plugin Name

Short description.

## Installation

...

## Usage

...

## Configuration

...

## Dependencies

...

## Platform Support

...

## Development

...
```

Plugin documentation should focus on the plugin itself. General Kapsel
concepts should link back to the main Kapsel documentation where possible.

---

# 🚀 Development Workflow

## 1. Create a Plugin

Use the repository's plugin synchronization script:

```bash
python scripts/sync_plugins.py --new <plugin_name>
```

This creates the standard plugin structure.

## 2. Implement the Plugin

Develop the plugin under:

```text
plugins/<plugin_name>/
```

Implement:

- plugin metadata;
- command registration;
- lifecycle hooks where required;
- external dependency installation where required;
- documentation;
- tests where applicable.

## 3. Test Locally

Enable the plugin in a local Kapsel environment:

```bash
kapsel add <plugin_name>
```

Then test its commands through:

```bash
kps <plugin_name>
```

Also verify the plugin's dependency installation behavior on every platform
you claim to support.

## 4. Synchronize the Repository

For official repository maintenance:

```bash
python scripts/sync_plugins.py <plugin_name>
```

## 5. Submit Changes

Create a branch, commit your changes, and open a pull request.

For community plugins, follow the contribution requirements described below.

---

# 🤝 Plugin Contribution

Kapsel welcomes third-party plugin contributions.

A community plugin should:

- provide a clear and focused purpose;
- use the supported Kapsel plugin interface;
- avoid modifying global shell configuration;
- follow the dependency installation policy;
- support all platforms it claims to support;
- include a useful README;
- avoid bundling unnecessary copies of external tools;
- use an appropriate open-source license;
- avoid malicious, destructive, or undisclosed behavior.

## Pull Request Checklist

Before submitting a plugin:

```text
[ ] Plugin structure follows the standard layout
[ ] Plugin entry point is valid
[ ] Commands use the supported Kapsel API
[ ] External dependencies are documented
[ ] Installation works on supported platforms
[ ] No unnecessary virtual environment is created
[ ] No shell startup files are modified
[ ] README.md is included
[ ] LICENSE is included
[ ] Basic functionality has been tested
```

Maintainers may request changes before a plugin is accepted into the official
ecosystem.

Community plugins remain maintained by their respective contributors unless
they are later adopted by the Kapsel maintainers.

---

# 🔐 Security

Plugins execute code on the user's machine and may invoke external programs.

Plugin authors must clearly document:

- external commands they execute;
- files or directories they modify;
- network access where applicable;
- credentials or environment variables they require;
- external services they communicate with.

Do not hide installation behavior or execute unrelated commands as part of
plugin setup.

If you discover a security issue in a plugin or in the plugin infrastructure,
please report it privately to the Kapsel maintainers rather than publishing
exploitation details in a public issue.

---

# 📄 License

Unless otherwise specified by an individual plugin, plugins in this
repository are released under the **MIT License**.

See each plugin's `LICENSE` file for its applicable license.

---

<div align="center">

**Build the capsule. Extend the ecosystem.**

</div>
