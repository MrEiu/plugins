# Profile Plugin for Kapsel

Cross-platform dotfile and environment configuration manager for **Kapsel**, powered by [chezmoi](https://www.chezmoi.io).

Manage, version-control, and synchronize configuration files (such as shell configs, git settings, and application profiles) across machines seamlessly.

## Installation

Add and enable the plugin via Kapsel system command:

```bash
kapsel add profile
```
*(Automatically ensures the official `chezmoi` executable is installed via Scoop/Homebrew/Winget or the official one-line install script).*

## Usage

### 1. Initialize Profile from Remote Repository
Clone and set up your dotfiles repository from GitHub:
```bash
kps profile init <github-username>
```

### 2. Apply and Synchronize Configuration
Apply all managed configuration files to the target machine:
```bash
kps profile apply
```

### 3. Track New Configuration Files
Add any local configuration to be managed by the profile plugin:
```bash
kps profile add ~/.gitconfig
kps profile add ~/.kapsel/config.yaml
```

### 4. Inspect State & Differences
```bash
# Check status of tracked files
kps profile status

# View diff between profile repo and current local machine
kps profile diff

# Pull latest remote changes and apply
kps profile update
```

## License
MIT License.
