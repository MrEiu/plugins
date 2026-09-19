# Help Plugin for Kapsel 📖⚡

Interactive multi-tool query & action workflow router for Kapsel shell.
Features zero-friction smart auto-inference, allowing you to run `kps help <anything>` to inspect ports, processes, DNS, HTTP, system specs, and command cheat sheets.

---

## 🚀 Smart Auto-Inference (`kps help <query>`)

You don't need to memorize distinct subcommands—simply pass your target directly to `kps help`:

| Target Query | Example | Auto-Routed Action |
|---|---|---|
| **Port number** (`<n>` or `:<n>`) | `kps help 8080` / `kps help :3000` | Inspect port listeners & kill occupying process |
| **URL** (`http://` or `https://`) | `kps help https://api.github.com` | Execute HTTP request, retry & save response |
| **Domain or IP** | `kps help github.com` / `kps help 8.8.8.8` | Resolve DNS, probe HTTP status & reverse PTR |
| **System keywords** | `kps help sys` / `kps help os` / `kps help cpu` | Display hardware specs, memory & OS summary |
| **Process keywords / PID** | `kps help ps` / `kps help pid:1234` | View active process table with interactive Kill menu |
| **Command name** | `kps help tar` / `kps help curl` | View cheat sheet + copy/run examples + locate binary |

---

## ⚡ Explicit Subcommands & Workflows

### 1. Port Occupancy & Process Termination
Inspect who is listening on a port and terminate it immediately:
```bash
# Check port 8080
kps help port 8080

# Kill process listening on port 8080 directly
kps help port 8080 --kill
```

### 2. Process Manager & Termination
View running processes and terminate unwanted PIDs:
```bash
# Filter processes by name
kps help ps node

# Kill by PID directly
kps help kill 14208
```

### 3. Command Usage & Example Execution
Lookup high-frequency examples, copy to clipboard (`[Enter]`), or execute directly (`[x]`):
```bash
kps help tar
kps help git commit
kps help docker
```

### 4. Binary Locator (`which` / `where`)
Locate the absolute executable path across system PATH, shims, and package managers:
```bash
kps help which python
kps help which node
```

### 5. DNS & Network Domain Resolver
Resolve IPv4/IPv6 addresses, probe HTTP connectivity, and reverse PTR lookups:
```bash
kps help dns github.com
kps help dns 1.1.1.1
```

### 6. HTTP Client & Response Saver
Send HTTP requests with formatted JSON syntax highlighting:
```bash
kps help http https://httpbin.org/get
```

### 7. HTTP Latency Waterfall (`stat`)
Measure DNS, TCP handshake, TLS negotiation, and TTFB latency phases:
```bash
kps help stat https://www.google.com
```

### 8. System Specification Card (`sys`)
View hardware architecture, CPU cores, memory status, and OS build:
```bash
kps help sys
```

### 9. Companion CLI Tools Checker (`install`)
Check installed tools and get recommended installation commands:
```bash
kps help install
```
