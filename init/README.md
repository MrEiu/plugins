# 🚀 Kapsel Init Plugin (powered by mise)

Project development environment initializer and polyglot runtime manager for Kapsel.
Bridges [mise-en-place (mise)](https://github.com/jdx/mise) to provide instant, reproducible dev environment setup under `kps init`.

---

## Features

- **One-command environment bootstrap**: `kps init` maps directly to `mise install` to install all declared runtimes and dev tools for the active workspace.
- **Polyglot runtime management**: Seamlessly install and lock versions for Node.js, Python, Go, Rust, Java, Deno, Bun, and 1,000+ tools.
- **Fast completions**: Dynamic auto-completion for common tools and subcommands.

---

## Commands

| Command | Description | Underlying mise mapping |
| :--- | :--- | :--- |
| `kps init` | Bootstrap and install all tools defined in project | `mise install` |
| `kps init <tool>@<version>` | Install a specific tool version (e.g. `node@22`) | `mise install <tool>@<version>` |
| `kps init use <tool>@<version>` | Pin and install tool into local project config | `mise use <tool>@<version>` |
| `kps init ls` / `kps init list` | List installed and active tool versions | `mise ls` |
| `kps init current` | Show currently active tool versions | `mise current` |
| `kps init doctor` | Diagnose environment and installation health | `mise doctor` |
| `kps init upgrade` | Upgrade outdated tools in current project | `mise upgrade` |
| `kps init run <task>` | Execute project tasks defined in `mise.toml` | `mise run <task>` |

---

## License

MIT
