# Help Plugin for Kapsel

Fast command cheat sheet lookup plugin for the **Kapsel** shell, powered by [tealdeer](https://github.com/tealdeer-rs/tealdeer) (a blazing fast implementation of `tldr` in Rust).

> **Important Distinction**:
> * `kapsel help` is Kapsel's internal system command manual (managing `status`, `config`, `add`, `datadir`).
> * `kps help` is this feature plugin providing instant cheat sheets and practical examples for thousands of CLI commands.

## Installation

Add and enable the plugin via Kapsel system command:

```bash
kapsel add help
```

*(Automatically installs `tealdeer` standalone static binary and initializes the local cheat sheet cache).*

## Usage

### 1. Command Quick Lookup (`kps help <command...>`)
Lookup practical examples and syntax for any tool:

```bash
kps help tar
kps help curl
kps help git commit
kps help docker run
```

### 2. Update Cheat Sheet Cache (`kps help --update`)
Keep your local copy of thousands of command pages updated from GitHub:

```bash
kps help --update
# or shorthand
kps help -u
```

### 3. List Available Pages (`kps help --list`)
List all available command documentation pages:

```bash
kps help --list
# or shorthand
kps help -l
```

### 4. Platform-Specific Cheat Sheets (`kps help -p <os>`)
Query cheat sheets tailored for specific operating systems:

```bash
kps help -p linux iptables
kps help -p macos brew
kps help -p windows netstat
```

## Interactive Auto-Completion

The plugin hooks into Kapsel's completion engine (`PROVIDE_COMPLETIONS`). Typing `kps help ` followed by letters dynamically provides matching command names from your local cache with instant response time.

## License

MIT License.
