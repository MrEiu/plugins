# 📦 Kapsel Plugin: Install (`kapsel-plugin-install`)

Official cross-platform package installer plugin for [Kapsel](https://github.com/kapsel-shell/Kapsel). It bridges [`meta-package-manager` (mpm)](https://github.com/kdeldycke/meta-package-manager) to provide unified package operations across 30+ package managers under the **`kps`** functional command space.

---

## 🚀 Features

- **Unified Installation (`kps install`)**: Install packages across systems (Scoop, Winget, Homebrew, APT, Pacman, etc.) without remembering system-specific syntax.
- **System-wide Update (`kps update`)**: Update packages across multiple active package managers with a single command.
- **Cross-Source Search (`kps search`)**: Search for packages across all active package managers simultaneously.
- **Package Configuration Sync (`kps sync -mpm`)**: Synchronize installed package states across devices via MPM.

---

## 📥 Installation

This plugin can be added and enabled into your Kapsel environment via:

```bash
kapsel add install
```

Make sure `meta-package-manager` is installed in your Python environment:

```bash
pip install meta-package-manager
```

---

## ⌨️ Command Usage

Once enabled, the plugin exposes the following functional commands:

### 1. Install Packages
```bash
kps install ripgrep
kps install neovim
```

### 2. Update Packages
```bash
kps update
```

### 3. Search Packages
```bash
kps search fzf
```

### 4. Sync Package Manager Configurations
```bash
# The -mpm flag is required to distinguish from future Kapsel cloud sync
kps sync -mpm
```

---

## 📄 License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
