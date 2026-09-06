"""
Default cross-platform alias mappings and Ultra Tools definitions for Kapsel.
Provides Linux-first universal aliases mapped to host shell native commands,
with progressive modern CLI tool enhancement (eza, bat, ripgrep, fd, procs, etc.).
All comments and descriptions are in English.
"""

from typing import Any, Dict, List

# Catalog of modern, high-performance CLI tools for 'kps alias ultra'
ULTRA_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "eza",
        "binary": "eza",
        "replaces": "ls / dir / ll",
        "desc": "Modern replacement for ls with Git status, file icons, and tree view",
        "scoop": "eza",
        "winget": "eza-community.eza",
        "brew": "eza",
        "cargo": "eza",
    },
    {
        "name": "bat",
        "binary": "bat",
        "replaces": "cat / type",
        "desc": "Cat clone with syntax highlighting and Git integration",
        "scoop": "bat",
        "winget": "sharkdp.bat",
        "brew": "bat",
        "cargo": "bat",
    },
    {
        "name": "ripgrep",
        "binary": "rg",
        "replaces": "grep / findstr",
        "desc": "Blazing fast recursive line-oriented regex search tool",
        "scoop": "ripgrep",
        "winget": "BurntSushi.ripgrep.MSVC",
        "brew": "ripgrep",
        "cargo": "ripgrep",
    },
    {
        "name": "fd",
        "binary": "fd",
        "replaces": "find / dir /s",
        "desc": "Simple, fast and user-friendly alternative to find",
        "scoop": "fd",
        "winget": "sharkdp.fd",
        "brew": "fd-find",
        "cargo": "fd-find",
    },
    {
        "name": "procs",
        "binary": "procs",
        "replaces": "ps / tasklist",
        "desc": "Modern replacement for ps with colorized output and Docker info",
        "scoop": "procs",
        "winget": "dalance.procs",
        "brew": "procs",
        "cargo": "procs",
    },
    {
        "name": "dust",
        "binary": "dust",
        "replaces": "du",
        "desc": "Intuitive graphical disk usage analyzer",
        "scoop": "dust",
        "winget": "bootandy.dust",
        "brew": "dust",
        "cargo": "du-dust",
    },
    {
        "name": "bottom",
        "binary": "btm",
        "replaces": "top / htop",
        "desc": "Cross-platform graphical process and system monitor",
        "scoop": "bottom",
        "winget": "Clement.bottom",
        "brew": "bottom",
        "cargo": "bottom",
    },
    {
        "name": "gping",
        "binary": "gping",
        "replaces": "ping",
        "desc": "Ping with a real-time graphical latency chart inside terminal",
        "scoop": "gping",
        "winget": "orf.gping",
        "brew": "gping",
        "cargo": "gping",
    },
    {
        "name": "jq",
        "binary": "jq",
        "replaces": "json filter",
        "desc": "Command-line JSON processor and stream slicer",
        "scoop": "jq",
        "winget": "jqlang.jq",
        "brew": "jq",
        "cargo": "",
    },
    {
        "name": "sd",
        "binary": "sd",
        "replaces": "sed",
        "desc": "Intuitive find & replace CLI, eliminating regex escaping pain",
        "scoop": "sd",
        "winget": "chmln.sd",
        "brew": "sd",
        "cargo": "sd",
    },
    {
        "name": "lazygit",
        "binary": "lazygit",
        "replaces": "git tui",
        "desc": "Simple terminal UI for git commands",
        "scoop": "lazygit",
        "winget": "JesseDuffield.lazygit",
        "brew": "lazygit",
        "cargo": "",
    },
    {
        "name": "hyperfine",
        "binary": "hyperfine",
        "replaces": "time benchmark",
        "desc": "Command-line benchmarking tool with warmups and statistical analysis",
        "scoop": "hyperfine",
        "winget": "sharkdp.hyperfine",
        "brew": "hyperfine",
        "cargo": "hyperfine",
    },
    {
        "name": "kondo",
        "binary": "kondo",
        "replaces": "clean dev builds",
        "desc": "CLI utility to save disk space by cleaning build artifacts (node_modules, target, .venv)",
        "scoop": "kondo",
        "winget": "tborychowski.kondo",
        "brew": "kondo",
        "cargo": "kondo",
    },
]

# Baseline 36+ Linux-First command mappings with progressive modern tool enhancement
DEFAULT_MAPPINGS: List[Dict[str, Any]] = [
    # --------------------------------------------------------------------------
    # 1. File & Directory Operations
    # --------------------------------------------------------------------------
    {
        "alias": "rm -rf",
        "desc": "Recursively and forcefully delete directories or files",
        "templates": {
            "pwsh": "Remove-Item -Recurse -Force {{args}}",
            "powershell": "Remove-Item -Recurse -Force {{args}}",
            "cmd": "rmdir /s /q {{args}}",
            "unix": "rm -rf {{args}}",
            "universal": "rm -rf {{args}}",
        },
    },
    {
        "alias": "rm",
        "desc": "Delete files or empty directories",
        "templates": {
            "pwsh": "Remove-Item {{args}}",
            "powershell": "Remove-Item {{args}}",
            "cmd": "del {{args}}",
            "unix": "rm {{args}}",
            "universal": "rm {{args}}",
        },
    },
    {
        "alias": "ls -la",
        "desc": "Detailed directory listing including hidden files and permissions",
        "modern_tool": "eza",
        "modern_template": "eza -la --icons {{args}}",
        "templates": {
            "pwsh": "Get-ChildItem -Force {{args}}",
            "powershell": "Get-ChildItem -Force {{args}}",
            "cmd": "dir /a {{args}}",
            "unix": "ls -la {{args}}",
            "universal": "ls -la {{args}}",
        },
    },
    {
        "alias": "ll",
        "desc": "Detailed list of files in directory with metadata",
        "modern_tool": "eza",
        "modern_template": "eza -l --icons {{args}}",
        "templates": {
            "pwsh": "Get-ChildItem -Force {{args}}",
            "powershell": "Get-ChildItem -Force {{args}}",
            "cmd": "dir {{args}}",
            "unix": "ls -l {{args}}",
            "universal": "ls -l {{args}}",
        },
    },
    {
        "alias": "ls",
        "desc": "List directory contents",
        "modern_tool": "eza",
        "modern_template": "eza {{args}}",
        "templates": {
            "pwsh": "Get-ChildItem {{args}}",
            "powershell": "Get-ChildItem {{args}}",
            "cmd": "dir /b {{args}}",
            "unix": "ls {{args}}",
            "universal": "ls {{args}}",
        },
    },
    {
        "alias": "cat",
        "desc": "Display file content or concatenate files",
        "modern_tool": "bat",
        "modern_template": "bat {{args}}",
        "templates": {
            "pwsh": "Get-Content {{args}}",
            "powershell": "Get-Content {{args}}",
            "cmd": "type {{args}}",
            "unix": "cat {{args}}",
            "universal": "cat {{args}}",
        },
    },
    {
        "alias": "touch",
        "desc": "Create a new empty file or update timestamp",
        "templates": {
            "pwsh": "New-Item -ItemType File -Force {{args}}",
            "powershell": "New-Item -ItemType File -Force {{args}}",
            "cmd": "type nul >> {{args}}",
            "unix": "touch {{args}}",
            "universal": "touch {{args}}",
        },
    },
    {
        "alias": "cp -r",
        "desc": "Recursively copy directory and contents",
        "templates": {
            "pwsh": "Copy-Item -Recurse -Force {{args}}",
            "powershell": "Copy-Item -Recurse -Force {{args}}",
            "cmd": "xcopy /e /i /y {{args}}",
            "unix": "cp -r {{args}}",
            "universal": "cp -r {{args}}",
        },
    },
    {
        "alias": "cp",
        "desc": "Copy file to destination",
        "templates": {
            "pwsh": "Copy-Item {{args}}",
            "powershell": "Copy-Item {{args}}",
            "cmd": "copy {{args}}",
            "unix": "cp {{args}}",
            "universal": "cp {{args}}",
        },
    },
    {
        "alias": "mv",
        "desc": "Move or rename files and directories",
        "templates": {
            "pwsh": "Move-Item -Force {{args}}",
            "powershell": "Move-Item -Force {{args}}",
            "cmd": "move {{args}}",
            "unix": "mv {{args}}",
            "universal": "mv {{args}}",
        },
    },
    {
        "alias": "mkdir -p",
        "desc": "Recursively create directory hierarchy",
        "templates": {
            "pwsh": "New-Item -ItemType Directory -Force {{args}}",
            "powershell": "New-Item -ItemType Directory -Force {{args}}",
            "cmd": "mkdir {{args}}",
            "unix": "mkdir -p {{args}}",
            "universal": "mkdir -p {{args}}",
        },
    },
    {
        "alias": "mkdir",
        "desc": "Create new directory",
        "templates": {
            "pwsh": "New-Item -ItemType Directory {{args}}",
            "powershell": "New-Item -ItemType Directory {{args}}",
            "cmd": "mkdir {{args}}",
            "unix": "mkdir {{args}}",
            "universal": "mkdir {{args}}",
        },
    },
    {
        "alias": "pwd",
        "desc": "Print absolute path of current working directory",
        "templates": {
            "pwsh": "Get-Location",
            "powershell": "Get-Location",
            "cmd": "cd",
            "unix": "pwd",
            "universal": "pwd",
        },
    },

    # --------------------------------------------------------------------------
    # 2. Text Search & Inspection
    # --------------------------------------------------------------------------
    {
        "alias": "grep",
        "desc": "Search text patterns using regular expressions",
        "modern_tool": "rg",
        "modern_template": "rg {{args}}",
        "templates": {
            "pwsh": "Select-String {{args}}",
            "powershell": "Select-String {{args}}",
            "cmd": "findstr {{args}}",
            "unix": "grep {{args}}",
            "universal": "grep {{args}}",
        },
    },
    {
        "alias": "find",
        "desc": "Recursively find files in directory tree",
        "modern_tool": "fd",
        "modern_template": "fd {{args}}",
        "templates": {
            "pwsh": "Get-ChildItem -Recurse -Filter {{args}}",
            "powershell": "Get-ChildItem -Recurse -Filter {{args}}",
            "cmd": "dir /s /b {{args}}",
            "unix": "find . -name {{args}}",
            "universal": "find . -name {{args}}",
        },
    },
    {
        "alias": "which",
        "desc": "Locate an executable or command path",
        "templates": {
            "pwsh": "Get-Command {{args}}",
            "powershell": "Get-Command {{args}}",
            "cmd": "where {{args}}",
            "unix": "which {{args}}",
            "universal": "which {{args}}",
        },
    },
    {
        "alias": "whereis",
        "desc": "Locate binary, source, and manual files for a command",
        "templates": {
            "pwsh": "Get-Command {{args}}",
            "powershell": "Get-Command {{args}}",
            "cmd": "where {{args}}",
            "unix": "whereis {{args}}",
            "universal": "whereis {{args}}",
        },
    },
    {
        "alias": "head",
        "desc": "Display first N lines of file",
        "templates": {
            "pwsh": "Get-Content -Head {{args}}",
            "powershell": "Get-Content -Head {{args}}",
            "cmd": "powershell -Command Get-Content -Head {{args}}",
            "unix": "head {{args}}",
            "universal": "head {{args}}",
        },
    },
    {
        "alias": "tail -f",
        "desc": "Follow dynamic output changes of a log file in real time",
        "templates": {
            "pwsh": "Get-Content -Wait -Tail 10 {{args}}",
            "powershell": "Get-Content -Wait -Tail 10 {{args}}",
            "cmd": "powershell -Command Get-Content -Wait -Tail 10 {{args}}",
            "unix": "tail -f {{args}}",
            "universal": "tail -f {{args}}",
        },
    },
    {
        "alias": "tail",
        "desc": "Display last N lines of file",
        "templates": {
            "pwsh": "Get-Content -Tail {{args}}",
            "powershell": "Get-Content -Tail {{args}}",
            "cmd": "powershell -Command Get-Content -Tail {{args}}",
            "unix": "tail {{args}}",
            "universal": "tail {{args}}",
        },
    },

    # --------------------------------------------------------------------------
    # 3. System & Process Management
    # --------------------------------------------------------------------------
    {
        "alias": "ps",
        "desc": "List currently active system processes",
        "modern_tool": "procs",
        "modern_template": "procs {{args}}",
        "templates": {
            "pwsh": "Get-Process {{args}}",
            "powershell": "Get-Process {{args}}",
            "cmd": "tasklist {{args}}",
            "unix": "ps aux {{args}}",
            "universal": "ps aux {{args}}",
        },
    },
    {
        "alias": "kill -9",
        "desc": "Forcefully terminate a process by PID",
        "templates": {
            "pwsh": "Stop-Process -Force -Id {{args}}",
            "powershell": "Stop-Process -Force -Id {{args}}",
            "cmd": "taskkill /f /pid {{args}}",
            "unix": "kill -9 {{args}}",
            "universal": "kill -9 {{args}}",
        },
    },
    {
        "alias": "kill",
        "desc": "Terminate a process by PID",
        "templates": {
            "pwsh": "Stop-Process -Id {{args}}",
            "powershell": "Stop-Process -Id {{args}}",
            "cmd": "taskkill /pid {{args}}",
            "unix": "kill {{args}}",
            "universal": "kill {{args}}",
        },
    },
    {
        "alias": "killall",
        "desc": "Terminate processes by program name",
        "templates": {
            "pwsh": "Stop-Process -Name {{args}} -Force",
            "powershell": "Stop-Process -Name {{args}} -Force",
            "cmd": "taskkill /f /im {{args}}",
            "unix": "killall {{args}}",
            "universal": "killall {{args}}",
        },
    },
    {
        "alias": "df -h",
        "desc": "Show filesystem disk space usage in human-readable units",
        "templates": {
            "pwsh": "Get-PSDrive -PSProvider FileSystem",
            "powershell": "Get-PSDrive -PSProvider FileSystem",
            "cmd": "wmic logicaldisk get caption, freespace, size",
            "unix": "df -h",
            "universal": "df -h",
        },
    },
    {
        "alias": "du",
        "desc": "Display disk space usage of files and directories",
        "modern_tool": "dust",
        "modern_template": "dust {{args}}",
        "templates": {
            "pwsh": "Get-ChildItem -Recurse {{args}} | Measure-Object -Property Length -Sum",
            "powershell": "Get-ChildItem -Recurse {{args}} | Measure-Object -Property Length -Sum",
            "cmd": "dir /s {{args}}",
            "unix": "du -sh {{args}}",
            "universal": "du -sh {{args}}",
        },
    },
    {
        "alias": "free -m",
        "desc": "Display system physical RAM and available memory in MB",
        "templates": {
            "pwsh": "Get-CimInstance Win32_OperatingSystem | Select-Object @{N='TotalMemoryMB';E={[math]::Round($_.TotalVisibleMemorySize/1024)}},@{N='FreeMemoryMB';E={[math]::Round($_.FreePhysicalMemory/1024)}}",
            "powershell": "Get-CimInstance Win32_OperatingSystem | Select-Object @{N='TotalMemoryMB';E={[math]::Round($_.TotalVisibleMemorySize/1024)}},@{N='FreeMemoryMB';E={[math]::Round($_.FreePhysicalMemory/1024)}}",
            "cmd": "systeminfo | findstr /C:\"Total Physical Memory\" /C:\"Available Physical Memory\"",
            "unix": "free -m",
            "universal": "free -m",
        },
    },
    {
        "alias": "uptime",
        "desc": "Show system boot timestamp and total elapsed runtime",
        "templates": {
            "pwsh": "(Get-Date) - (Get-CimInstance Win32_OperatingSystem).LastBootUpTime",
            "powershell": "(Get-Date) - (Get-CimInstance Win32_OperatingSystem).LastBootUpTime",
            "cmd": "net stats srv",
            "unix": "uptime",
            "universal": "uptime",
        },
    },
    {
        "alias": "uname -a",
        "desc": "Show system OS architecture, build version, and caption",
        "templates": {
            "pwsh": "Get-CimInstance Win32_OperatingSystem | Select-Object Caption, Version, OSArchitecture",
            "powershell": "Get-CimInstance Win32_OperatingSystem | Select-Object Caption, Version, OSArchitecture",
            "cmd": "ver",
            "unix": "uname -a",
            "universal": "uname -a",
        },
    },
    {
        "alias": "whoami",
        "desc": "Print active user identity and privileges",
        "templates": {
            "pwsh": "whoami.exe",
            "powershell": "whoami.exe",
            "cmd": "whoami",
            "unix": "whoami",
            "universal": "whoami",
        },
    },
    {
        "alias": "clear",
        "desc": "Clear the terminal screen buffer",
        "templates": {
            "pwsh": "Clear-Host",
            "powershell": "Clear-Host",
            "cmd": "cls",
            "unix": "clear",
            "universal": "clear",
        },
    },
    {
        "alias": "env",
        "desc": "Display active session environment variables",
        "templates": {
            "pwsh": "Get-ChildItem env:",
            "powershell": "Get-ChildItem env:",
            "cmd": "set",
            "unix": "env",
            "universal": "env",
        },
    },
    {
        "alias": "printenv",
        "desc": "Print all or specified environment variables",
        "templates": {
            "pwsh": "Get-ChildItem env:{{args}}",
            "powershell": "Get-ChildItem env:{{args}}",
            "cmd": "set {{args}}",
            "unix": "printenv {{args}}",
            "universal": "printenv {{args}}",
        },
    },

    # --------------------------------------------------------------------------
    # 4. Networking & Diagnostics
    # --------------------------------------------------------------------------
    {
        "alias": "ifconfig",
        "desc": "Display local active network interfaces and IPv4 addresses",
        "templates": {
            "pwsh": "Get-NetIPAddress -AddressFamily IPv4 | Format-Table InterfaceAlias, IPAddress",
            "powershell": "Get-NetIPAddress -AddressFamily IPv4 | Format-Table InterfaceAlias, IPAddress",
            "cmd": "ipconfig",
            "unix": "ifconfig",
            "universal": "ifconfig",
        },
    },
    {
        "alias": "ip a",
        "desc": "Display all network interfaces, status, and IP addresses",
        "templates": {
            "pwsh": "Get-NetIPAddress | Format-Table InterfaceAlias, IPAddress",
            "powershell": "Get-NetIPAddress | Format-Table InterfaceAlias, IPAddress",
            "cmd": "ipconfig /all",
            "unix": "ip a",
            "universal": "ip a",
        },
    },
    {
        "alias": "ping",
        "desc": "Send ICMP echo requests to network hosts",
        "modern_tool": "gping",
        "modern_template": "gping {{args}}",
        "templates": {
            "pwsh": "Test-Connection {{args}}",
            "powershell": "Test-Connection {{args}}",
            "cmd": "ping {{args}}",
            "unix": "ping {{args}}",
            "universal": "ping {{args}}",
        },
    },
    {
        "alias": "curl -O",
        "desc": "Download remote file saving with original remote filename",
        "templates": {
            "pwsh": "curl.exe -O {{args}}",
            "powershell": "curl.exe -O {{args}}",
            "cmd": "curl.exe -O {{args}}",
            "unix": "curl -O {{args}}",
            "universal": "curl -O {{args}}",
        },
    },

    # --------------------------------------------------------------------------
    # 5. Archive & Compression
    # --------------------------------------------------------------------------
    {
        "alias": "tar -czvf",
        "desc": "Create a tar.gz compressed archive from directories or files",
        "templates": {
            "pwsh": "tar.exe -czvf {{args}}",
            "powershell": "tar.exe -czvf {{args}}",
            "cmd": "tar.exe -czvf {{args}}",
            "unix": "tar -czvf {{args}}",
            "universal": "tar -czvf {{args}}",
        },
    },
    {
        "alias": "tar -xzvf",
        "desc": "Extract a tar.gz compressed archive into current directory",
        "templates": {
            "pwsh": "tar.exe -xzvf {{args}}",
            "powershell": "tar.exe -xzvf {{args}}",
            "cmd": "tar.exe -xzvf {{args}}",
            "unix": "tar -xzvf {{args}}",
            "universal": "tar -xzvf {{args}}",
        },
    },
    {
        "alias": "open",
        "desc": "Open file or URL using the default system application",
        "templates": {
            "pwsh": "Invoke-Item {{args}}",
            "powershell": "Invoke-Item {{args}}",
            "cmd": "start {{args}}",
            "unix": "open {{args}}",
            "universal": "open {{args}}",
        },
    },
]


def get_default_aliases() -> List[Dict[str, Any]]:
    """Returns a copy of the default alias mappings list."""
    return list(DEFAULT_MAPPINGS)

