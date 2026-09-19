# Backup Plugin for Kapsel 🛡️

Lightweight zero-pollution file & folder version backup and interactive restoration CLI powered by **GitKeep**.

---

## ⚡ Highlights

- **Zero Project Pollution**: Never creates any `.git` folder or config files inside your workspace. All repositories are safely isolated in your home directory (`~/.gitkeep/`).
- **Zero Configuration**: Ready to use immediately. Run `bk` to create your initial backup snapshot.
- **Interactive Restore Menu**: Simply run `bk restore` without arguments to launch a terminal arrow-key picker (`[↑/↓]` to select, `[Enter]` to restore).
- **Fast Standalone & NPM Engine**: Powered by `gitkeep-cli` available on npm, plus optional compiled binaries (`gitkeep/dist/bk.exe`).
- **Non-Destructive Rollbacks**: Restoration creates forward commits without destroying Git history.

---

## 📦 Installation

Install `gitkeep-cli` globally using your preferred package manager:

```bash
# npm
npm install -g gitkeep-cli

# pnpm
pnpm add -g gitkeep-cli

# bun
bun add -g gitkeep-cli

# yarn
yarn global add gitkeep-cli
```

Or run the built-in auto-installer directly inside Kapsel:
```bash
bk install
# or
kps backup install
```

---

## 🚀 Quick Start

### 1. Instant Backup
```bash
# Backup current directory immediately
bk

# Backup with a custom message (no -m flag required!)
bk "updated training hyperparameters"

# Backup a specific file or subfolder
bk data/ "synced raw dataset"
bk config.json "bumped version"
```

### 2. View History & Changes
```bash
# View backup commit history with friendly relative timestamps
bk log

# View changes made since latest backup
bk diff
```

### 3. One-Command Instant Undo
```bash
# Instantly roll back to previous backup version
bk undo
```

### 4. Interactive Snapshot Restoration
```bash
# Interactive selection menu (arrow keys + Enter)
bk restore

# Direct restoration using commit hash or short hash
bk restore a1b2c3d
```

### 5. Multi-Project & Status Inspection
```bash
# Check current directory binding status and unique 8-character ID
bk status

# List all registered backup projects on this computer
bk list
```

---

## ⌨️ Command Aliases

The plugin registers and intercepts the following command variations:

| Command Pattern | Action |
| :--- | :--- |
| `bk [args...]` | Quick backup & version management |
| `backup [args...]` | Alias for `bk` |
| `kps bk [args...]` | Explicit Kapsel plugin command |
| `kps backup [args...]` | Explicit Kapsel plugin command |

---

## ⚙️ Architecture

```text
Your Workspace (e.g. C:\Users\meru6\Desktop\Project)
├── src/
└── data/                       <--- 100% clean (NO .git)

                    │
                    ▼
Centralized Storage (~/.gitkeep/ or C:\Users\<user>\.gitkeep\)
├── registry.json               <--- Maps Project path -> Unique 8-char ID
└── repos/<id>/                 <--- Dedicated isolated Git repository
```
