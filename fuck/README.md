# Fuck Plugin for Kapsel

Intelligent console command auto-correction plugin for the **Kapsel** shell, powered by [thefuck](https://github.com/nvbn/thefuck).

## Overview

When you mistype a console command (e.g. `puthon`, `git br`, `sl`), simply type:

```bash
kps fuck
```

The plugin analyzes your previous failed command, determines the correct syntax, presents an interactive correction menu, and automatically executes the fixed command upon confirmation.

## Installation

Install and enable the plugin via Kapsel system command:

```bash
kapsel add fuck
```

*(Automatically installs `thefuck`, configures Python 3.12+ compatibility shims, and creates runtime launchers).*

## Usage

### 1. Interactive Auto-Correction (`kps fuck`)
After typing an invalid command:
```bash
$ git br
git: 'br' is not a git command. See 'git --help'.

$ kps fuck
git branch [enter/↑/↓/ctrl+c]
➜ git branch
* master
```

### 2. Immediate Execution (`kps fuck -y` or `--yes`)
Auto-correct and immediately execute without confirmation:
```bash
kps fuck -y
# or
kps fuck --yes
```

### 3. Fix Explicit Command (`kps fuck <command...>`)
You can also supply the command directly:
```bash
kps fuck git br
kps fuck -y git comit -m "Fix typo"
```

### 4. Additional Options
* **Show help**: `kps fuck --help`
* **Show version**: `kps fuck --version`
* **Show shell alias snippet**: `kps fuck --alias`

## Python 3.12+ Compatibility

The plugin includes automated runtime shims for modern Python versions (3.12, 3.13+) where the legacy `imp` standard library module was removed, ensuring error-free operation on all platforms.

## License

MIT License.
