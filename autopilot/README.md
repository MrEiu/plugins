# Autopilot Plugin for Kapsel

Autonomous background task queue and daemon execution manager for the **Kapsel** shell, powered by [Pueue](https://github.com/Nukesor/pueue).

The plugin enables developers to enqueue long-running commands (builds, tests, downloads, data migrations, training jobs) in the background, monitor task queues, inspect logs, and stream real-time terminal output without blocking the current interactive session.

---

## Key Features

- **Zero-Friction Daemon Auto-Start**: Automatically launches `pueued -d` in the background on demand. You will never encounter "daemon not running" errors.
- **Background Task Enqueueing**: Dispatch any command to the background queue with a simple `kps auto add <command>`.
- **Rich Status Dashboard**: Visual terminal dashboard with status badges, worker concurrency, and execution durations.
- **Log Streaming & Inspection**: Check past task outputs with `kps auto log <id>` or follow live stdout/stderr streams like `tail -f` with `kps auto follow <id>`.
- **Task Lifecycle Control**: Pause, resume, restart, and kill tasks or entire groups.
- **Dynamic Context Autocompletion**: Auto-completes subcommands and live task IDs with command summaries and status indicators.

---

## Installation

Add and enable the plugin via Kapsel system command:

```bash
kapsel add autopilot
```

*(Automatically detects and installs `pueue` via Scoop, Winget, or Cargo if not present).*

---

## Usage

### 1. Dashboard Overview (`kps auto`)

Run `kps auto` without arguments to view the active queue overview and command guide:

```bash
kps auto
```

### 2. Enqueueing Background Tasks (`kps auto add <command...>`)

Send long-running tasks to run asynchronously in the background:

```bash
kps auto add npm run build
kps auto add cargo build --release
kps auto add python scripts/train_model.py
```

Natural shortcut syntax is also supported:

```bash
kps auto "docker compose up -d"
```

### 3. Checking Queue Status (`kps auto status`)

View full task status, including queue positions and execution times:

```bash
kps auto status
```

For programmatic pipelines, get structured JSON output:

```bash
kps auto status --json
```

### 4. Inspecting Logs (`kps auto log` & `kps auto follow`)

View stdout and stderr from a completed task:

```bash
kps auto log 0
```

Follow a currently running task's output stream live:

```bash
kps auto follow 0
```

### 5. Controlling Task Execution

```bash
kps auto pause 0          # Pause task #0
kps auto start 0          # Resume task #0
kps auto restart 0        # Re-run task #0
kps auto kill 0           # Terminate task #0
kps auto clean            # Remove all successfully finished tasks from history
kps auto reset            # Kill all running tasks and reset entire queue
```

### 6. Concurrency & Daemon Management

```bash
kps auto parallel 4       # Allow up to 4 tasks to run in parallel
kps auto daemon status    # Check Pueue background service status
kps auto daemon restart   # Restart the Pueue background daemon
```

---

## Autocompletion

Tab completion dynamically suggests:
- Core subcommands: `add`, `status`, `log`, `follow`, `pause`, `start`, `restart`, `kill`, `clean`, `daemon`, etc.
- Active & recent task IDs: `kps auto log <Tab>` will display task numbers alongside their command snippets and status icons (`🟢 Running`, `✔ Done`, `❌ Failed`).
