# Preview Plugin for Kapsel

**Preview** (`kps preview`, shortcut `prev`) is a universal, smart terminal file and directory preview dispatcher for Kapsel.

It dispatches preview requests to 10 dedicated, industry-standard CLI power tools based on file types. It operates purely in the terminal without full-screen TUI locks, and provides instant error feedback if a tool is missing without inaccurate approximations.

---

## 10-Category Preview Matrix

| Category | File Types | Dedicated CLI Tool | Preview Experience |
| :--- | :--- | :--- | :--- |
| **Code & Text** | `.py`, `.rs`, `.go`, `.js`, `.ts`, `.c`, `.sh`, etc. | **bat** | Syntax highlighting, line numbers, git diff markers |
| **Markdown** | `.md`, `.markdown`, `.rst` | **glow** | Rich terminal markdown rendering, tables, headers |
| **Structured Data** | `.json`, `.json5`, `.jsonl` | **jq** | Colored syntax, formatted indentation |
| **Tabular Data** | `.csv`, `.tsv` | **xsv** | Aligned grid terminal tables |
| **Directories** | Any directory / folder | **eza** (or `tree`) | Tree structure, file size, permissions, icons |
| **Archives** | `.zip`, `.tar`, `.gz`, `.7z`, etc. | **7z** (or `tar`) | Archive content listing without unpacking |
| **Images** | `.png`, `.jpg`, `.webp`, `.svg`, `.gif` | **chafa** | High-fidelity terminal character / Sixel graphics |
| **PDF Documents** | `.pdf` | **pdftoppm + chafa** (or `pdf-cli` / `pdftotext`) | High-fidelity visual terminal rendering via Sixel / TrueColor (supports `-p <page>`) |
| **Media Metadata** | `.mp4`, `.mkv`, `.mp3`, `.wav`, etc. | **mediainfo** (or `ffprobe`) | Codecs, duration, bitrate, resolution |
| **Hex / Binaries** | `.exe`, `.dll`, `.bin`, `.so`, etc. | **xxd** (or `hexdump`) | Hex and ASCII byte offset dump |

---

## Strict Dispatch (No Inaccurate Fallbacks)

If a specialized tool is not installed, Kapsel Preview cleanly reports the missing tool and prints installation hints (e.g. `scoop install <tool>` or `brew install <tool>`). It deliberately avoids low-fidelity text dumps so users always get the highest preview quality.

---

## Installation

```bash
# Add preview plugin
kps add preview

# Verify and check all 10 tools
kps install preview
```

---

## Usage

```bash
# Quick preview (auto-detects file type and launches tool)
prev main.py
prev README.md
prev data.csv
prev document.pdf
prev ./src

# Limit preview lines
prev -l 50 large_file.py

# Full output
prev -a file.log

# Explicit command
kps preview document.pdf
```

---

## Interactive Directory Mode (`fm`)

Preview integrates a native, zero-dependency 3-column Miller Columns file manager:

```bash
# Launch directory mode in current working directory
fm

# Launch in specific directory or focus specific file
fm ./src
fm README.md

# Explicit command
kps preview fm [path]
```

### Keyboard Navigation in `fm`

| Key | Action |
| :--- | :--- |
| `h` / `←` | Ascend to parent directory |
| `j` / `↓` | Move cursor down (instant live preview on right) |
| `k` / `↑` | Move cursor up (instant live preview on right) |
| `l` / `→` / `Enter` | Enter folder, or open file with default editor/viewer |
| `c` | **Teleport (cd)**: Exit and switch Kapsel terminal working directory to selected folder |
| `q` / `Esc` | Quit without changing directory |

