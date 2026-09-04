"""
Default cross-platform alias mappings for Kapsel.
Provides Linux-first universal aliases mapped to host shell native commands.
All comments and descriptions are in English.
"""

from typing import Any, Dict, List

DEFAULT_MAPPINGS: List[Dict[str, Any]] = [
    {
        "alias": "rm -rf",
        "desc": "Recursively and forcefully delete directories or files",
        "templates": {
            "pwsh": "Remove-Item -Recurse -Force {{args}}",
            "powershell": "Remove-Item -Recurse -Force {{args}}",
            "cmd": "rmdir /s /q {{args}}",
            "unix": "rm -rf {{args}}",
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
        },
    },
    {
        "alias": "ls -la",
        "desc": "Detailed directory listing including hidden items",
        "templates": {
            "pwsh": "Get-ChildItem -Force {{args}}",
            "powershell": "Get-ChildItem -Force {{args}}",
            "cmd": "dir /a {{args}}",
            "unix": "ls -la {{args}}",
        },
    },
    {
        "alias": "ll",
        "desc": "Detailed list of files in directory",
        "templates": {
            "pwsh": "Get-ChildItem -Force {{args}}",
            "powershell": "Get-ChildItem -Force {{args}}",
            "cmd": "dir {{args}}",
            "unix": "ls -l {{args}}",
        },
    },
    {
        "alias": "ls",
        "desc": "List directory contents",
        "templates": {
            "pwsh": "Get-ChildItem {{args}}",
            "powershell": "Get-ChildItem {{args}}",
            "cmd": "dir /b {{args}}",
            "unix": "ls {{args}}",
        },
    },
    {
        "alias": "cat",
        "desc": "Display file content or concatenate files",
        "templates": {
            "pwsh": "Get-Content {{args}}",
            "powershell": "Get-Content {{args}}",
            "cmd": "type {{args}}",
            "unix": "cat {{args}}",
        },
    },
    {
        "alias": "touch",
        "desc": "Create a new empty file or update timestamp",
        "templates": {
            "pwsh": "New-Item -ItemType File -Force {{args}}",
            "powershell": "New-Item -ItemType File -Force {{args}}",
            "cmd": "type nul > {{args}}",
            "unix": "touch {{args}}",
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
        },
    },
    {
        "alias": "grep",
        "desc": "Search text patterns using regular expressions",
        "templates": {
            "pwsh": "Select-String {{args}}",
            "powershell": "Select-String {{args}}",
            "cmd": "findstr {{args}}",
            "unix": "grep {{args}}",
        },
    },
    {
        "alias": "find",
        "desc": "Recursively find files in directory tree",
        "templates": {
            "pwsh": "Get-ChildItem -Recurse -Filter {{args}}",
            "powershell": "Get-ChildItem -Recurse -Filter {{args}}",
            "cmd": "dir /s /b {{args}}",
            "unix": "find . -name {{args}}",
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
        },
    },
    {
        "alias": "df -h",
        "desc": "Show filesystem disk space usage in human readable format",
        "templates": {
            "pwsh": "Get-PSDrive -PSProvider FileSystem",
            "powershell": "Get-PSDrive -PSProvider FileSystem",
            "cmd": "wmic logicaldisk get caption, freespace, size",
            "unix": "df -h",
        },
    },
    {
        "alias": "ps",
        "desc": "List currently active system processes",
        "templates": {
            "pwsh": "Get-Process {{args}}",
            "powershell": "Get-Process {{args}}",
            "cmd": "tasklist {{args}}",
            "unix": "ps aux {{args}}",
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
        },
    },
    {
        "alias": "clear",
        "desc": "Clear the terminal screen",
        "templates": {
            "pwsh": "Clear-Host",
            "powershell": "Clear-Host",
            "cmd": "cls",
            "unix": "clear",
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
        },
    },
]
