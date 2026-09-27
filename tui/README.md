# Kapsel TUI Plugin (`kps tui`)

Full-screen developer workbench and split TUI for **Kapsel**, featuring a permanent workspace file tree, native multi-tab PTY terminal, and Web-grade Textual UI shell.

---

## Key Features

- **Permanent Workspace File Tree**: Clean file explorer with category icons (`📁`, `π`, `◇`, `#`), fast keyboard navigation, and Enter-to-insert path injection.
- **Native Embedded PTY Terminal**: Full ANSI color, VT100/Xterm emulation, and native interactive shell fidelity via `pyte` + `winpty` (Windows) / `ptyprocess` (POSIX).
- **Multi-Tab Terminal Sessions**: Spawn and manage multiple terminal tabs concurrently with live status dots (`🟢`, `🟡`, `🟣`).
- **Universal Tab Leader-Key System**:
  - `[Tab]` (single tap): Switch focus between **Left File Tree ⟷ Right Terminal**.
  - `[Tab + T]`: Create new Terminal Tab.
  - `[Tab + W]`: Close active Terminal Tab.
  - `[Tab + B]`: Toggle collapse / expand File Tree sidebar.
  - `[Tab + 1..9]`: Jump directly to Tab #1..#9.
  - `[Tab + Q]`: Quit TUI safely and reap all background processes.
  - `[⬇]` (Down Arrow): Dedicated to terminal autocomplete candidates.

---

## Installation

Add and enable the plugin via Kapsel:

```bash
kapsel add tui
```

---

## Usage

Launch the workbench in the current directory:

```bash
kps tui
```

Or open a specific workspace directory:

```bash
kps tui /path/to/project
```
