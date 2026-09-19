# Queue Plugin for Kapsel

Autonomous background task queue and daemon execution manager for the **Kapsel** shell, powered by [Pueue](https://github.com/Nukesor/pueue).

The plugin enables developers to enqueue long-running commands (builds, tests, downloads, data migrations, training jobs) in the background, monitor task queues, inspect logs, and stream real-time terminal output without blocking the current interactive session.

---

## Key Features

- **Zero-Friction Daemon Auto-Start**: Automatically launches `pueued -d` in the background on demand. You will never encounter "daemon not running" errors.
- **Background Task Enqueueing**: Dispatch any command to the background queue with a simple `kps queue add <command>`.
- **Rich Status Dashboard**: Visual terminal dashboard with status badges, worker concurrency, and execution durations.
- **Log Streaming & Inspection**: Check past task outputs with `kps queue log <id>` or follow live stdout/stderr streams like `tail -f` with `kps queue follow <id>`.
- **Task Lifecycle Control**: Pause, resume, restart, and kill tasks or entire groups.
- **Dynamic Context Autocompletion**: Auto-completes subcommands and live task IDs with command summaries and status indicators.
- **Backwards Compatibility**: Both `kps queue` and legacy `kps auto` commands are fully supported.

---

## Installation

Add and enable the plugin via Kapsel system command:

```bash
kapsel add queue
```

*(Automatically detects and installs `pueue` via Scoop, Winget, or Cargo if not present).*

---

## Usage

### 1. Dashboard Overview (`kps queue` / `kps auto`)

Run `kps queue` without arguments to view the active queue overview and command guide:

```bash
kps queue
```

### 2. Enqueueing Background Tasks (`kps queue add <command...>`)

Send long-running tasks to run asynchronously in the background:

```bash
kps queue add npm run build
kps queue add cargo build --release
kps queue add python scripts/train_model.py
```

Natural shortcut syntax is also supported:

```bash
kps queue "docker compose up -d"
```

### 3. Checking Queue Status (`kps queue status`)

View full task status, including queue positions and execution times:

```bash
kps queue status
```

For programmatic pipelines, get structured JSON output:

```bash
kps queue status --json
```

### 4. Inspecting Logs (`kps queue log` & `kps queue follow`)

View stdout and stderr from a completed task:

```bash
kps queue log 0
```

Follow a currently running task's output stream live:

```bash
kps queue follow 0
```

### 5. Controlling Task Execution

```bash
kps queue pause 0          # Pause task #0
kps queue start 0          # Resume task #0
kps queue restart 0        # Re-run task #0
kps queue kill 0           # Terminate task #0
kps queue clean            # Remove all successfully finished tasks from history
kps queue reset            # Kill all running tasks and reset entire queue
```

### 6. Concurrency & Daemon Management

```bash
kps queue parallel 4       # Allow up to 4 tasks to run in parallel
kps queue daemon status    # Check Pueue background service status
kps queue daemon restart   # Restart the Pueue background daemon
```

---

## Autocompletion

Tab completion dynamically suggests:
- Core subcommands: `add`, `status`, `log`, `follow`, `pause`, `start`, `restart`, `kill`, `clean`, `daemon`, etc.
- Active & recent task IDs: `kps queue log <Tab>` will display task numbers alongside their command snippets and status icons (`🟢 Running`, `✔ Done`, `❌ Failed`).
