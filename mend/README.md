# Kapsel Mend Plugin (`kps mend`)

Diagnostic self-healing health checker and interactive configuration cleaner for Kapsel.

## Features

1. **Concurrent Plugin Dependency Health Check**:
   - Concurrently verifies external CLI tool dependencies across all installed plugins using a 4-thread worker pool.
   - Inspects physical executable locations across PATH, Scoop shims, WinGet links, Kapsel local bin (`~/.kapsel/bin/`), and Cargo bin.
   - Generates an actionable diagnostic matrix table showing ready vs missing tools.
   - Automatically repairs missing tools via declarative strategies (`kps mend fix`).

2. **Interactive Configuration & Storage Cleaner**:
   - Scans historical session and debug logs (`~/.kapsel/logs/*.log`).
   - Scans temporary downloads and leftover binaries (`~/.kapsel/bin/download_*`).
   - Scans stale configuration snapshots (`~/.kapsel/*.bak`, `*.old`).
   - Scans plugin cache directories (`~/.kapsel/plugins_data/*/cache`).
   - Scans Python bytecode caches (`__pycache__`).
   - Offers interactive arrow-key checkbox multi-selection with safe confirmation.

## Commands

```bash
# Check all plugin dependencies
kps mend
kps mend check

# Check and auto-install all missing tool dependencies
kps mend check --fix
kps mend fix

# Interactively clean logs, backup configs, and caches
kps mend clean

# Run both health check and storage cleaner
kps mend all
```
