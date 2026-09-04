# Alias Plugin for Kapsel

Multi-terminal and cross-platform command alias mapping plugin for the **Kapsel** shell.

Translates universal Linux-first commands (e.g. `rm -rf`, `ll`, `cat`, `touch`, `grep`, `which`, `ps`, `ifconfig`, `df -h`) into host shell native commands (such as PowerShell, CMD, or Bash).

## Installation

Add and enable the plugin via Kapsel system command:

```bash
kapsel add alias
```

## Usage

### 1. Transparent Execution
Prepend `kps` before universal aliases, and Kapsel automatically translates and executes them natively:

```bash
# In PowerShell: translates to Remove-Item -Recurse -Force node_modules
kps rm -rf node_modules

# In PowerShell: translates to Get-ChildItem -Force
kps ll

# In PowerShell: translates to New-Item -ItemType File -Force app.py
kps touch app.py

# In PowerShell: translates to Select-String "error" app.log
kps grep "error" app.log
```

### 2. Alias Management Commands
* **List active mappings**: `kps alias list` (or `kps alias`)
* **Test / Preview translation**: `kps alias test rm -rf build/`
* **Add a custom mapping**: `kps alias add 'git-clean' 'git clean -fdx'`
* **Remove a mapping**: `kps alias remove 'git-clean'`
* **Reset to baseline**: `kps alias reset`

## License
MIT License.
