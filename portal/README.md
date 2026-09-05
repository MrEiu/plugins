# Portal Plugin for Kapsel

**Portal** is an intelligent directory teleportation and workspace navigator plugin for Kapsel, powered by **[zoxide](https://github.com/ajeetdsouza/zoxide)**.

It remembers the directories you use most frequently based on *frecency* (frequency + recency), allowing you to jump to complex directory paths with only a few keystrokes.

---

## Features

- ⚡ **Instant Jump**: Type `z <keywords>` or `portal <keywords>` directly in the Kapsel terminal (e.g. `z kap` jumps straight to `~/Desktop/Kapsel`).
- 🧠 **Zero-Config Auto-Learning**: Automatically updates frecency rankings as you work via Kapsel lifecycle hooks.
- 📊 **Workspace Ranking**: Inspect tracked directories and scores with `kps portal ls`.
- 📂 **Native File Explorer Integration**: Open target directories in Windows Explorer or macOS Finder with `kps portal open [keywords]`.
- 🔍 **Interactive Autocomplete**: Injects candidate directory paths into Kapsel prompt completions.
- 🛠️ **Cross-Platform**: Full support for Windows (PowerShell/CMD), macOS, and Linux.

---

## Installation

```bash
# Enable portal plugin in Kapsel
kps add portal
```

If `zoxide` is not already installed on your system, `install.py` will automatically install it via Scoop, WinGet, Homebrew, Cargo, or download prebuilt binaries.

---

## Usage

### In Kapsel Terminal (Direct Jumping)

```bash
# Jump to best matching directory
z kapsel
z kap

# Standard directory navigation
z                  # Jump to home directory (~)
z -                # Jump to previous directory
z ..               # Go up one level
```

### Management Suite (`kps portal`)

| Command | Description |
| :--- | :--- |
| `kps portal ls [query]` | View ranked directories with frecency scores |
| `kps portal add [path]` | Register current or target directory |
| `kps portal rm <path>` | Remove a directory from the database |
| `kps portal query <keywords>` | Resolve and print the best matching path |
| `kps portal open [query]` | Open target directory in File Explorer / Finder |
| `kps portal doctor` | Check zoxide version, database path, and health |
| `kps portal edit` | Directly edit zoxide database |
| `kps portal init [shell]` | Generate external shell hook snippet |
| `kps portal --help` | View help panel and examples |

---

## License

MIT License.
