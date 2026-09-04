# 🔌 Kapsel 官方插件仓库开发规范 (Plugins Repository Guide)

欢迎来到 Kapsel 官方插件家族仓库（Monorepo: `https://github.com/MrEiu/plugins`）。
本文档面向所有插件开发者与维护者，详细规范插件结构、生命周期以及**外部依赖工具的安装策略**。

---

## 🌟 核心依赖安装准则 (Dependency Philosophy)

> 📌 **铁律准则：**
> 1. **首选 `kps install`**：虽然**绝大部分工具直接使用 `kps install <tool>` 都能解决**（依托底层 MPM 统一调动系统的各大主流包管理器，如 Scoop, Winget, Homebrew, Apt, Pacman 等）。
> 2. **链式正规安装，严禁虚拟环境**：当工具依赖某一个特定的包管理工具（如 Python CLI 工具依赖 `pipx`，Rust CLI 工具依赖 `cargo`）时，**如果系统缺乏该包管理工具，就必须“先安装该包管理工具，然后再安装该目标工具”**。**严禁在插件中自搞虚拟环境（venv）或非标准临时目录等乱七八糟的做法**，确保用户系统环境的整洁、规范与全局一致性。
> 3. **多平台差异化定制**：安装脚本**必须严格针对不同操作系统平台（Windows / macOS / Linux）设置针对性的安装方案与优雅降级策略**。

---

## 📁 插件标准目录结构

每个插件为一个独立的自闭环包目录：

```text
plugins/<plugin_name>/
├── __init__.py           # 导出 Plugin = MyPlugin 类
├── plugin.py             # 核心逻辑：继承 KapselPlugin，注册 kps 指令与生命周期钩子
├── install.py            # 【独立依赖安装脚本】按平台差异化安装包管理器与目标工具
├── pyproject.toml        # 插件包元数据与依赖定义
├── README.md             # 插件完整英文使用文档与用例
└── LICENSE               # 许可协议（MIT）
```

---

## 🛠 跨平台安装方案矩阵 (Cross-Platform Matrix)

编写 `install.py` 时，需遵循以下平台适配矩阵：

| 操作系统 | 优先方案 | 链式依赖方案（如缺少包管理器） | 终极兜底方案 |
| :--- | :--- | :--- | :--- |
| **Windows** | `kps install <tool>` / `scoop install` / `winget install` | 若依赖 pipx：先 `pip install pipx` -> 再 `pipx install <tool>` | 官方 Release 静态预编译二进制下载到 `~/.kapsel/bin/` |
| **macOS** | `kps install <tool>` / `brew install <tool>` | 若依赖 pipx：先 `brew install pipx` -> 再 `pipx install <tool>` | 官方 Release (x86_64 / arm64) 静态二进制 |
| **Linux** | `kps install <tool>` / 发行版包管 (`apt`, `pacman`, `dnf`) | 若依赖 pipx：先系统包管装 pipx -> 再 `pipx install <tool>` | 官方 musl / glibc 独立二进制 |

---

## 📝 标准 `install.py` 模板

在插件根目录下创建 `install.py`，对外导出统一接口 `def install(console: Console, bin_dir: Path) -> bool`：

```python
"""
Installer for <PluginName> dependencies.
Adheres to Kapsel chain installation philosophy:
Package Manager First -> Target Tool Next -> Cross-platform tailored.
"""

from pathlib import Path
import platform
import shutil
import subprocess
import sys
from rich.console import Console


def install(console: Console, bin_dir: Path) -> bool:
    """
    Standard plugin installation entrypoint:
    1. Check if tool already exists in PATH
    2. Try kps install / native package managers (Brew, Scoop, Winget, Apt)
    3. If relying on a package manager (e.g. pipx) that is missing:
       Install that package manager first, then install the tool!
    """
    tool_name = "<tool_name>"
    if shutil.which(tool_name):
        console.print(f"[dim]✔ {tool_name} is already installed.[/]")
        return True

    system = platform.system().lower()
    console.print(f"[bold #00f0ff]📦 Installing {tool_name} for platform: {system}...[/]")

    # 1. 尝试统一包管理器 kps install / 系统原生包管
    if shutil.which("kps"):
        res = subprocess.run(["kps", "install", tool_name], stdout=subprocess.DEVNULL)
        if res.returncode == 0 and shutil.which(tool_name):
            return True

    # 2. macOS / Linux 优先 Homebrew
    if system in ("darwin", "linux") and shutil.which("brew"):
        res = subprocess.run(["brew", "install", tool_name], stdout=subprocess.DEVNULL)
        if res.returncode == 0 and shutil.which(tool_name):
            return True

    # 3. 链式安装：若工具依赖 pipx，缺乏时先安装 pipx，再通过 pipx 安装目标工具
    if not shutil.which("pipx"):
        console.print("[dim]  Required package manager 'pipx' missing. Installing pipx first...[/]")
        if system == "windows":
            subprocess.run([sys.executable, "-m", "pip", "install", "pipx", "--quiet"])
        elif shutil.which("brew"):
            subprocess.run(["brew", "install", "pipx"])
        else:
            subprocess.run([sys.executable, "-m", "pip", "install", "pipx", "--quiet"])

    if shutil.which("pipx") or shutil.which("pipx.exe"):
        console.print(f"[dim]  Installing {tool_name} using pipx...[/]")
        subprocess.run(["pipx", "install", tool_name])
        return bool(shutil.which(tool_name))

    # 4. 终极兜底：预编译单文件 Release (可选)
    # 若无法通过包管理器安装，可从官方发布页下载独立二进制放入 bin_dir

    console.print(f"[bold #f43f5e]✘ Automatic installation failed for {tool_name}.[/]")
    return False
```

---

## 🚀 插件开发与发布流程

1. **新建插件脚手架**：
   ```bash
   python scripts/sync_plugins.py --new <plugin_name>
   ```
2. **本地测试与启用**：
   ```bash
   kapsel add <plugin_name>
   ```
3. **同步并推送到 GitHub 插件仓库**：
   ```bash
   python scripts/sync_plugins.py <plugin_name> --push
   ```
