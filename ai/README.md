# AI Plugin for Kapsel

Terminal AI assistant plugin for the **Kapsel** shell, powered by [aichat](https://github.com/sigoden/aichat).

The plugin provides instant single-turn natural language queries, shell command generation and execution (`-e`), code generation (`-c`), and a user-friendly interactive setup wizard (`kps ai init`) that configures modern LLM providers (DeepSeek, Ollama, SiliconFlow, OpenAI, Gemini, Claude, and custom endpoints) effortlessly.

> **Design Note**:
> Bare `kps ai` displays an informative help and syntax guide with prompt examples instead of dropping you into an interactive REPL session, keeping your terminal responsive and workflow focused.

---

## Installation

Add and enable the plugin via Kapsel system command:

```bash
kapsel add ai
```

*(Automatically installs `aichat` via Scoop, Winget, Homebrew, or binary download if not already present on your system).*

---

## Quick Setup (`kps ai init`)

Run Kapsel's guided interactive setup wizard to configure your preferred LLM provider and API key in seconds:

```bash
kps ai init
```

The wizard guides you through:
1. **Model Provider Selection**:
   - `1` - DeepSeek (`deepseek-chat` / `deepseek-coder` / `deepseek-reasoner`)
   - `2` - Ollama (Local LLM, no API key required, e.g. `llama3`, `deepseek-r1`)
   - `3` - SiliconFlow (Fast Chinese domestic API gateway)
   - `4` - OpenAI (`gpt-4o`, `gpt-4o-mini`, `o1`)
   - `5` - Google Gemini (`gemini-1.5-pro`, `gemini-1.5-flash`)
   - `6` - Anthropic Claude (`claude-3-5-sonnet-20241022`)
   - `7` - Custom OpenAI-compatible API (OneAPI, NewAPI, vLLM, FastChat)
2. **API Key & Endpoint Configuration**: Safe input prompts for your credentials and custom URLs.
3. **Model Selection & Connection Test**: Automatically saves configuration isolated under Kapsel's data directory (`$KAPSEL_DATA_DIR/ai/config.yaml`) and verifies network connectivity.

---

## Usage

### 1. Direct Question / Prompt (`kps ai <prompt...>`)

Ask questions, request summaries, or explain concepts directly in your terminal:

```bash
kps ai "Explain how Docker container networking works"
kps ai "What is the difference between TCP and UDP?"
kps ai "Write a regular expression matching ISO 8601 timestamps"
```

### 2. Natural Language Shell Command Execution (`kps ai -e <prompt...>`)

Generate executable terminal commands from plain English descriptions and optionally execute them directly:

```bash
kps ai -e "find all .log files modified in the last 7 days and sort by size"
kps ai -e "kill all processes listening on port 8080"
kps ai -e "compress the src directory into a tar.gz archive"
```

### 3. Code-Only Output (`kps ai -c <prompt...>`)

Generate pure code without conversational text or markdown explanation, ideal for piping into files or tools:

```bash
kps ai -c "python script to fetch title and headers from a web page"
kps ai -c "bash function to check if a command exists in PATH"
```

### 4. Configuration Management (`kps ai config`)

Inspect, test, or open the configuration file:

```bash
kps ai config status   # Check configured model, provider, and config path
kps ai config test     # Send a ping test to verify LLM API connectivity
kps ai config edit     # Open config.yaml in your system's default editor
```

---

## Configuration Details

The plugin keeps its configuration cleanly isolated in the Kapsel workspace/data directory:
- Config path: `$KAPSEL_DATA_DIR/ai/config.yaml`
- Automatically mirrors to standard system paths (`%APPDATA%\aichat\config.yaml` on Windows or `~/.config/aichat/config.yaml` on Linux/macOS) for maximum interoperability with standalone `aichat` invocations.

---

## License

MIT License.
