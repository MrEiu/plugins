# ⛵ Shore Plugin for Kapsel

**Shore** is a blazing-fast, intelligent mirror source switcher plugin for Kapsel, powered by [chsrc (Change Source)](https://github.com/RubyMetric/chsrc).

It enables one-click auto-benchmarking and switching to the fastest mirror source across programming languages, package managers, and operating systems.

---

## 🚀 Features

- **Auto Benchmark & Select (`kps shore set <dish>`)**: Pings candidate mirrors and automatically selects the fastest one.
- **Shorthand Mode (`kps shore <dish>`)**: Direct one-click speedtest and switch (e.g. `kps shore py`, `kps shore npm`, `kps shore cargo`).
- **Targeted Mirror (`kps shore set <dish> <mirror>`)**: Explicitly switch to a known mirror (e.g. `tuna`, `aliyun`, `ustc`, `tencent`, `huawei`).
- **Inspect Configuration (`kps shore get <dish>`)**: Check the currently active mirror URL and configuration status.
- **Reset to Upstream (`kps shore reset <dish>`)**: Restore official default upstream sources.
- **Speed Measurement (`kps shore measure <dish>`)**: Speed-test and rank all mirrors with latency and download speeds.
- **Deep Autocompletion**: Tab completion for all dishes, mirrors, and categories.

---

## 📦 Supported Ecosystems

| Category | Popular Supported Targets (Dishes) |
| :--- | :--- |
| **Python** | `python`, `pip`, `uv`, `poetry`, `pdm`, `rye`, `conda` |
| **Node.js** | `npm`, `pnpm`, `yarn`, `bun`, `node`, `nvm` |
| **Rust & Go** | `cargo`, `rustup`, `go` |
| **Package Managers** | `brew`, `scoop`, `winget`, `docker`, `cocoapods` |
| **JVM & .NET** | `maven`, `gradle`, `nuget` |
| **Mobile** | `flutter`, `dart` |
| **Linux OS** | `ubuntu`, `debian`, `arch`, `fedora`, `alpine` |

---

## 🛠 Usage Examples

```bash
# Auto benchmark and switch to the fastest Python mirror
kps shore py

# Explicitly switch Node.js npm to Tsinghua TUNA mirror
kps shore set npm tuna

# Inspect current Cargo mirror
kps shore get cargo

# Speed-test all available mirrors for Docker
kps shore measure docker

# Reset uv back to official default index
kps shore reset uv

# List all available mirror providers
kps shore list mirror
```

---

## 📄 License

MIT License.
