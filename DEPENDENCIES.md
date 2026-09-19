# Kapsel 本体与全插件外部工具依赖清单 (Dependencies Manifest)

本文档将 **Kapsel 终端生态**（本体核心 + 全部 18 个官方插件）所涉及的全部外部依赖，严格按照 **5 大交付与安装类别** 进行清晰划归与整理：

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        外部工具与依赖 5 大分类                          │
├────────────────────────────────────────────────────────────────────────┤
│  1. 系统内置 (不需要安装)       → OS 开箱即用 (curl, netstat, tasklist)│
│  2. OS 包管理器                → scoop / winget / brew / apt / pacman   │
│  3. 语言包管理器               → npm / pip / cargo (CLI 工具与包)       │
│  4. 官方预编译二进制           → GitHub Releases 独立免安装可执行单文件 │
│  5. 官方一键安装脚本           → curl ... | sh / irm ... | iex         │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 一、系统内置（不需要安装）

这类工具由操作系统（Windows、macOS、Linux）或 Python 标准运行时默认提供，**完全零安装成本，开箱即用**：

| 工具名称 | 对应插件/功能 | 核心用途 | 所在操作系统 / 提供方 |
|---|---|---|---|
| **`netstat`** | `help port` | 端口监听与 TCP/UDP 连接状态查询 | Windows、macOS、Linux 全内置 |
| **`tasklist` / `ps`** | `help ps` | 查看正在运行的进程列表与内存占用 | Windows (`tasklist`) / Unix (`ps`) 内置 |
| **`taskkill` / `kill`** | `help kill`, `help port` | 终止指定 PID 进程 | Windows (`taskkill`) / Unix (`kill`) 内置 |
| **`nslookup` / `dig`** | `help dns` | 基础 DNS 域名与反向 PTR 解析 | 各系统内置（Windows 默认带 `nslookup`） |
| **`curl`** | `help http`, `update` | HTTP/HTTPS 连通测试与文件传输 | Win10+、macOS、Linux 全内置 |
| **`clip` / `pbcopy` / `xclip`** | `commit`, `help`, `locate` | 剪贴板复制（路径、示例代码、提交信息） | Windows (`clip`) / macOS (`pbcopy`) 内置 |
| **`where` / `which`** | `help which`, `help where` | 探测可执行文件绝对路径与别名 | Windows (`where.exe`) / Unix (`which`) 内置 |
| **`PowerShell` / `chcp`** | `lang` | 终端文化代码页与多语言环境即时切换 | Windows 平台内置 |
| **`socket` / `urllib` / `platform`** | `help`, `ai` | 优雅降级网络探测、HTTP 请求与系统硬件规格收集 | Python 3.10+ 标准库内置（零三方依赖） |

---

## 二、OS 包管理器（OS Package Managers）

这类工具推荐通过操作系统原生或主流用户级包管理器安装（**Windows: `scoop` / `winget`**，**macOS: `brew`**，**Linux: `apt` / `pacman`**）：

| 工具名称 | 对应插件 | 核心功能与使用场景 | Windows (Scoop) | macOS (Homebrew) | Linux (APT/Pacman) |
|---|---|---|---|---|---|
| **`fastfetch`** | `help sys` | 高性能现代软硬件规格展示 | `scoop install fastfetch` | `brew install fastfetch` | `snap install fastfetch` / pacman |
| **`jq`** | `preview`, `help` | 极速 JSON 结构化查询与格式化渲染 | `scoop install jq` | `brew install jq` | `apt install jq` |
| **`fd`** | `portal` | 极速全盘文件/目录模糊遍历 | `scoop install fd` | `brew install fd` | `apt install fd-find` / pacman |
| **`zoxide`** | `portal` | 目录智能学习与秒级传送 (`z`) | `scoop install zoxide` | `brew install zoxide` | `pacman -S zoxide` |
| **`eza`** | `preview` | 现代文件与目录树形列表展示 | `scoop install eza` | `brew install eza` | `pacman -S eza` |
| **`bat`** | `preview` | 语法高亮代码与文本查看器 | `scoop install bat` | `brew install bat` | `apt install bat` |
| **`glow`** | `preview` | Markdown 终端富文本渲染器 | `scoop install glow` | `brew install glow` | `brew install glow` |
| **`xsv`** | `preview` | CSV / TSV 表格数据极速切片查看 | `scoop install xsv` | `brew install xsv` | `pacman -S xsv` |
| **`7z` / `7zz`** | `preview` | 压缩包 (zip, 7z, tar) 目录树透视 | `scoop install 7zip` | `brew install sevenzip` | `apt install p7zip-full` |
| **`chafa`** | `preview` | 终端高保真块/Sixel/Kitty 图像渲染 | `scoop install chafa` | `brew install chafa` | `apt install chafa` |
| **`poppler`** (`pdftoppm`) | `preview` | PDF 页面矢量转位图光栅化 | `scoop install poppler` | `brew install poppler` | `apt install poppler-utils` |
| **`ffmpeg`** | `preview` | 音视频元数据与关键帧提取缩略图 | `scoop install ffmpeg` | `brew install ffmpeg` | `apt install ffmpeg` |
| **`imagemagick`** | `preview` | 图像、字体标本渲染与格式转换 | `scoop install imagemagick` | `brew install imagemagick` | `apt install imagemagick` |
| **`resvg`** | `preview` | SVG 矢量图终端光栅化渲染 | `scoop install resvg` | `brew install resvg` | `cargo install resvg` |
| **`procs`** | `help ps` | 现代化彩色进程查看与搜索器 | `scoop install procs` | `brew install procs` | `pacman -S procs` |
| **`xh`** | `help http` | 现代化友好极速 HTTP 客户端 | `scoop install xh` | `brew install xh` | `pacman -S xh` |
| **`doggo`** | `help dns` | 人性化现代 DNS 客户端与色彩分析 | `scoop install doggo` | `brew install doggo` | `pacman -S doggo` |
| **`chezmoi`** | `profile` | 跨平台点文件与配置文件同步管理 | `scoop install chezmoi` | `brew install chezmoi` | `brew install chezmoi` |
| **`pet`** | `rec` | 命令行片段记录备忘与模糊执行 | `scoop install pet` | `brew install pet` | `brew install pet` |
| **`translate-shell`** | `trans` | 强大的命令行多引擎翻译工具 | — (Windows用fanyi) | `brew install translate-shell` | `apt install translate-shell` |

---

## 三、语言包管理器（npm / pip / cargo）

这类工具以各自编程语言生态分发，用户只需安装对应运行时（Node.js / Python / Rust）即可全局安装：

### 1. Node.js 生态 (`npm` / `pnpm` / `bun` / `yarn`)
| 包名称 | 暴露命令 | 对应插件 | 核心用途 | 一键安装命令 |
|---|---|---|---|---|
| **`gitkeep-cli`** | `bk`, `backup`, `gitkeep` | `backup` | 零污染独立 Git 文件夹快照备份与交互式版本还原 | `npm install -g gitkeep-cli` |
| **`pm2`** | `pm2` | `autopilot` | 常驻生产进程守护、服务多实例与健康监控 | `npm install -g pm2` |
| **`fanyi`** | `fanyi` | `trans` | Windows 平台原生快速多翻译引擎 CLI | `npm install -g fanyi` |

### 2. Python 生态 (`pip` / `pipx`)
| 包名称 | 暴露命令 | 对应插件 | 核心用途 | 一键安装命令 |
|---|---|---|---|---|
| **`meta-package-manager`**| `mpm` | `install` | 统一抽象与驱动全平台数十种包管理器 | `pip install meta-package-manager` |
| **`thefuck`** | `thefuck`, `fuck` | `fuck` | 终端命令拼写错误智能修复与自动替换 | `pip install thefuck` |
| **`httpstat`** | `httpstat` | `help stat` | HTTP 请求传输时延、TLS握手与TTFB瀑布分析 | `pip install httpstat` |
| **`openai`** | *(Python SDK)* | `ai` | 终端 AI 智能助手核心接口 | `pip install openai` |

### 3. Rust 生态 (`cargo install`)
| 包名称 | 暴露命令 | 对应插件 | 核心用途 | 一键安装命令 |
|---|---|---|---|---|
| **`tealdeer`** | `tldr` | `help` | Rust 编写的极致高性能 tldr 手册客户端 | `cargo install tealdeer` |
| **`pueue`** | `pueue`, `pueued` | `queue` | 极简后台任务队列客户端与长任务守护进程 | `cargo install pueue` |

---

## 四、官方预编译独立二进制（GitHub Releases / 免安装单文件）

此类工具无需配置复杂的构建环境，官方直接提供编译好的平台原生独立单文件（`.exe` / 无依赖可执行文件），下载后直接放置在 `~/.kapsel/bin/` 或系统 PATH 中即可运行：

| 工具名称 | 对应插件 / 本体 | 官方发布渠道 | 为什么适合独立二进制 |
|---|---|---|---|
| **`carapace`** | **Kapsel 本体核心** | [carapace-bin Releases](https://github.com/carapace-sh/carapace-bin/releases) | **Kapsel 会全自动下载**并放入 `~/.kapsel/bin/carapace`，抹平跨 Shell 补全差异 |
| **`tealdeer`** (`tldr`) | `help` | [tealdeer Releases](https://github.com/tealdeer-rs/tealdeer/releases) | 单文件纯静态二进制，启动 <10ms，官方全平台编译包直接可用 |
| **`gitkeep-cli`** (`bk.exe`) | `backup` | 本地源码 / GitHub Release | 可使用 Bun 预编译为单文件 `bk.exe`，无需 Node.js 环境直接运行 |
| **`chsrc`** | `shore` | [chsrc Releases](https://github.com/RubyMetric/chsrc/releases) | 极致纯 C 单文件静态编译，只有几 MB，解压即用 |
| **`pueue` & `pueued`** | `queue` | [pueue Releases](https://github.com/Nukesor/pueue/releases) | 官方为 Windows、macOS、Linux 均打包好了零依赖客户端与服务端守护程序 |
| **`pet`** | `rec` | [pet Releases](https://github.com/knqyf263/pet/releases) | Go 编写的单二进制工具，解压即走 |
| **`chezmoi`** | `profile` | [chezmoi Releases](https://github.com/twpayne/chezmoi/releases) | 单文件 Go 编译二进制，跨终端便携度极高 |

---

## 五、官方一键安装脚本（curl ... | sh / irm ... | iex）

工具官方维护的一键管道脚本，能在没有任何预置包管理器的全新系统上，毫秒级自动适配 CPU 架构并完成安装：

| 工具名称 | 对应插件 | 平台 | 官方安装单行命令 |
|---|---|---|---|
| **`chsrc`** | `shore` | **Windows** (PowerShell) | `irm https://chsrc.run/win \| iex` |
|  |  | **Linux / macOS** (Bash) | `curl -fsSL https://chsrc.run \| bash` |
| **`mise`** | `init` | **Windows** (PowerShell) | `irm https://mise.run/powershell \| iex` |
|  |  | **Linux / macOS** (Bash) | `curl https://mise.run \| sh` |
| **`zoxide`** | `portal` | **Linux / macOS / WSL** | `curl -sSfL https://raw.githubusercontent.com/ajeetdsouza/zoxide/main/install.sh \| sh` |
| **`carapace`** | **Kapsel 本体** | 全平台 | 由 Kapsel 内部自动安装（或 `kps install carapace`） |

---

## 六、全插件依赖速查矩阵 (18 个插件全覆盖)

| 插件名 | 1. 系统内置 | 2. OS 包管理器 | 3. 语言包管理器 | 4. 预编译二进制 | 5. 官方安装脚本 |
|:---|:---:|:---:|:---:|:---:|:---:|
| **`ai`** | ✅ Python stdlib | — | ✅ `pip install openai` | — | — |
| **`alias`** | ✅ Shell native | — | — | ✅ `carapace` | — |
| **`autopilot`**| — | — | ✅ `npm i -g pm2` | — | — |
| **`backup`** | ✅ `git` | — | ✅ `npm i -g gitkeep-cli` | ✅ 可独立编译 `bk.exe` | — |
| **`commit`** | ✅ `git`, 剪贴板 | — | — | — | — |
| **`fuck`** | — | ✅ `scoop`/`brew` 可选 | ✅ `pip install thefuck` | — | — |
| **`help`** | ✅ `netstat`,`tasklist` | ✅ `procs`,`xh`,`doggo` | ✅ `pip install httpstat` | ✅ `tealdeer` 单文件 | — |
| **`init`** | — | ✅ `scoop`/`brew` 可选 | — | — | ✅ `curl https://mise.run \| sh` |
| **`install`** | — | — | ✅ `pip install meta-package-manager` | — | — |
| **`lang`** | ✅ `PowerShell`/`chcp`| — | — | — | — |
| **`portal`** | — | ✅ `scoop install zoxide fd` | — | — | ✅ `zoxide` 官方脚本 |
| **`preview`** | — | ✅ `bat`,`glow`,`jq`,`eza`等 | — | — | — |
| **`profile`** | — | ✅ `scoop install chezmoi` | — | ✅ `chezmoi` 单文件 | — |
| **`queue`** | — | ✅ `scoop install pueue` | ✅ `cargo install pueue` | ✅ `pueue` 官方 Release | — |
| **`rec`** | — | ✅ `scoop install pet` | — | ✅ `pet` 官方 Release | — |
| **`shore`** | — | ✅ `scoop install chsrc` | — | ✅ `chsrc` 官方 Release | ✅ `curl https://chsrc.run \| bash` |
| **`template`**| ✅ `git` | — | 可选 `cookiecutter`/`copier` | — | — |
| **`trans`** | — | ✅ `translate-shell` (Unix) | ✅ `npm i -g fanyi` (Win) | — | — |
| **`update`** | ✅ `git`, `curl` | — | — | — | — |
