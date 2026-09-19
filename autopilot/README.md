# Autopilot Plugin for Kapsel (PM2 Process Supervisor)

Production process manager, cluster supervisor, and daemon orchestrator for the **Kapsel** shell, powered by [PM2](https://pm2.keymetrics.io/).

Autopilot empowers developers and DevOps engineers to manage microservices, background workers, web servers, and automation scripts with zero-downtime rolling reloads, automatic crash recovery, multi-runtime execution, and real-time observability.

---

## Key Features

- **Polyglot Multi-Runtime Execution**: Run Node.js, Python, TypeScript, Bash/Shell scripts, or compiled binaries (Go, Rust). Autopilot automatically infers and attaches appropriate interpreters (e.g. `python`, `bash`, `tsx`).
- **Cluster Mode & Zero-Downtime Reload (`kps ap reload`)**: Scale Node.js applications across all CPU cores with automatic load balancing. Perform rolling updates without dropping active HTTP/TCP client connections.
- **Self-Healing & Memory Watchdog**: Guard against memory leaks with `--max-memory-restart <size>` (e.g. `300M`), exponential crash backoff delays, and auto-restart on boot.
- **Rich Aesthetic Dashboard (`kps ap`)**: Cyberpunk/Neon styled terminal overview displaying PID, mode, CPU usage, memory consumption, uptime, and restart counts at a glance.
- **Dynamic Context Autocompletion**: Live Carapace integration that dynamically queries `pm2 jlist` to suggest active process names and IDs with status badges (`🟢 online`, `🔴 errored`, `⏸️ stopped`) and live CPU/memory metrics.
- **Declarative Ecosystem Generation (`kps ap init`)**: Generates a battle-tested `ecosystem.config.cjs` template ready for multi-service environments.
- **System Boot Persistence**: Snapshot and restore running processes across reboots with `kps ap save`, `kps ap resurrect`, and `kps ap startup`.
- **Integrated Terminal Observability**: Full-screen interactive dashboard via `kps ap monit`, plus real-time aggregated log streaming via `kps ap follow`.

---

## Installation

Install and enable the plugin via Kapsel system command:

```bash
kapsel add autopilot
```

*(Automatically detects and installs PM2 globally via npm, pnpm, yarn, Scoop, or Homebrew if not already installed).*

Manual installation via npm:

```bash
npm install -g pm2
```

---

## Usage

Both `kps autopilot` and the short ergonomic alias `kps ap` are supported.

### 1. Visual Dashboard Overview (`kps ap`)

Run `kps ap` without arguments to inspect all active processes and daemon metrics:

```bash
kps ap
```

### 2. Starting Scripts and Services (`kps ap start`)

Start any script or application. The runtime interpreter is automatically detected:

```bash
# Node.js
kps ap start server.js --name web-api

# Python worker (automatically uses python interpreter)
kps ap start scripts/worker.py --name data-sync

# Cluster mode scaling across all CPU cores
kps ap start server.js -i max --name cluster-api

# Memory limit auto-restart & file watch
kps ap start app.js --max-memory-restart 300M --watch

# Declarative ecosystem configuration
kps ap start ecosystem.config.cjs
```

### 3. Zero-Downtime Rolling Reload (`kps ap reload`)

For cluster applications, reload workers one-by-one with zero downtime:

```bash
kps ap reload web-api
kps ap reload all
```

### 4. Process Lifecycle Management

```bash
# Stop a process
kps ap stop web-api
kps ap stop 0
kps ap stop all

# Restart a process
kps ap restart web-api

# Delete a process from PM2
kps ap delete web-api
kps ap delete all
```

### 5. Inspecting Logs & Observability

```bash
# View last 50 lines of logs
kps ap logs web-api --lines 50

# Follow live output stream in real time (tail -f style)
kps ap follow web-api

# Clear log files
kps ap flush web-api

# Full-screen interactive ncurses terminal monitor
kps ap monit

# Detailed metadata, environment, and paths
kps ap describe web-api
```

### 6. System Persistence & Boot Auto-Start

```bash
# Snapshot active process state to disk (~/.pm2/dump.pm2)
kps ap save

# Restore process snapshot after system restart
kps ap resurrect

# Configure OS init service (systemd, Windows service, launchd)
kps ap startup
```

### 7. Generating Ecosystem Config Template (`kps ap init`)

Generate a clean, modern `ecosystem.config.cjs` template:

```bash
kps ap init
```

---

## Dynamic Autocompletion

Tab completion dynamically suggests:
- Core subcommands: `start`, `stop`, `restart`, `reload`, `delete`, `logs`, `follow`, `monit`, `describe`, `save`, `resurrect`, `init`, `status`.
- Active process targets: `kps ap restart <Tab>` or `kps ap logs <Tab>` dynamically lists running process names and numeric IDs with real-time status badges (`🟢 online`, `🔴 errored`, `⏸️ stopped`), current CPU%, and memory usage.
