# Kapsel Translate Plugin (`trans` / `tr`)

Seamless terminal command output translation and multilingual dictionary powered by:
- **Windows**: [`fanyi`](https://github.com/afc163/fanyi) (native Node.js translation with dictionary, phonetics, and LLM).
- **macOS / Linux**: [`translate-shell`](https://github.com/soimort/translate-shell) (`trans`) or `fanyi`.

## Features

- 🌐 **Instant Post-Command Translation**: Type `tr` (or press `Alt + T`) right after any command to translate its stdout/stderr into Chinese.
- ⚡ **Pipeline Translation**: Pipe any CLI output directly into translation: `<cmd> | tr`.
- 🔤 **Smart Bidirectional Auto-Detection**: Translates English to Simplified Chinese by default, and Chinese to English.
- 🎨 **Rich Bilingual Cards**: Beautiful terminal presentation of original output vs translated meaning.

## Installation of Core Dependency

### Windows
```powershell
npm install -g fanyi
# or
pnpm add -g fanyi
```

### macOS
```bash
brew install translate-shell
# or
npm install -g fanyi
```

### Linux
```bash
sudo apt install translate-shell    # Debian / Ubuntu
sudo pacman -S translate-shell      # Arch Linux
# or
npm install -g fanyi
```

## Usage

### 1. Translate Output of Previous Command
```bash
# After a command finishes or fails:
tr
# or press Alt + T
```

### 2. Stream Command Output Through Pipeline
```bash
docker logs my-app | tr
pytest --help | tr
curl https://api.github.com/zen | tr
```

### 3. Translate Arbitrary Text
```bash
tr "fatal: remote origin already exists."
tr "repository"
```
