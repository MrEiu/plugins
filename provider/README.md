# Provider Plugin for Kapsel (`kps provider`)

Direct transparent wrapper for `cc-switch` ([SaladDay/cc-switch-cli](https://github.com/SaladDay/cc-switch-cli) v5.10.5).

Manage and switch providers, models, and proxy endpoints for Claude Code, Codex, OpenCode, and local AI agent runtimes.

## Usage

```bash
# Launch interactive TUI menu
kps provider

# Run any native cc-switch CLI command directly
kps provider list
kps provider use <name>
kps provider set <name> [options]
kps provider test [name]
kps provider --help
```

## Installation of cc-switch-cli

If not automatically installed:

- **Scoop**: `scoop install cc-switch-cli`
- **Homebrew**: `brew install cc-switch-cli`
- **Cargo**: `cargo install cc-switch-cli`
- **npm**: `npm install -g cc-switch-cli`
