# AI Copilot Plugin for Kapsel

Native terminal AI assistant plugin for the **Kapsel** shell, powered directly by the official [OpenAI Python SDK](https://github.com/openai/openai-python).

Zero external binaries, lightning-fast streaming, and purpose-built for developer workflows directly inside your terminal.

---

## Features

- **`kps ai <prompt>` / `kps ai do <prompt>`**: Natural language to shell command generation with 1-click interactive execution (`[Enter]` run, `[Tab/e]` copy to clipboard, `[Esc/q]` cancel).
- **`kps ai fix` / `kps ai ?`**: Auto-diagnoses the last failed command from Kapsel's `BlockRegistry` (analyzing command, exit code, and error output) and suggests a 1-click auto-repair.
- **`kps ai commit`**: Inspects `git diff` / staged changes, generates Conventional Commits messages, and prompts for 1-click `git commit -m`.
- **`kps ai explain [cmd]`**: Step-by-step breakdown of shell commands, parameters, and flags.
- **`<cmd> | kps ai [prompt]`**: Real-time terminal pipeline stream processor.
- **`kps ai scout`**: Workspace reconnaissance analyzing project manifests (`package.json`, `Cargo.toml`, `pyproject.toml`, etc.) to brief tech stack, architecture, and run commands.
- **`kps ai init`**: Interactive guided configuration wizard supporting DeepSeek, SiliconFlow, Ollama, Gemini, OpenAI, and custom endpoints.
- **`kps ai config [status|test|model <name>|edit]`**: Inspect, test connectivity, switch active models, or edit configuration.

---

## Quick Setup (`kps ai init`)

Run the setup wizard to connect your preferred provider:

```bash
kps ai init
```

Supported providers:
1. **DeepSeek** (Official API: `deepseek-chat`, `deepseek-reasoner`)
2. **SiliconFlow / 硅基流动** (`DeepSeek-V3`, `DeepSeek-R1`, `Qwen2.5-72B`)
3. **Ollama** (Local offline LLM, no API key needed: `deepseek-r1`, `llama3.3`, `qwen2.5-coder`)
4. **Google Gemini** (Official OpenAI-compatible endpoint: `gemini-2.0-flash`, `gemini-1.5-pro`)
5. **OpenAI** (Official API: `gpt-4o`, `gpt-4o-mini`, `o3-mini`)
6. **Custom Endpoint** (OneAPI, NewAPI, vLLM, FastChat, etc.)

---

## Usage Examples

### 1. Natural Language Command Copilot
```bash
kps ai list all docker containers created today
kps ai do kill process on port 8080
```
Outputs the exact command for your OS/shell and prompts:
- Press `[Enter]` to execute immediately
- Press `[Tab]` or `[e]` to copy to clipboard for editing
- Press `[Esc]` or `[q]` to cancel

### 2. Auto-Fix Last Failed Command
```bash
# A command failed with non-zero exit code
kps ai fix
# or simply:
kps ai ?
```

### 3. Git Diff to Conventional Commit
```bash
git add .
kps ai commit
```

### 4. Command Dissection
```bash
kps ai explain tar -czvf archive.tar.gz ./src
```

### 5. Workspace Reconnaissance
```bash
kps ai scout
```

### 6. Pipeline Stream Processing
```bash
cat build.log | kps ai summarize errors and warnings
```

---

## Configuration

Configuration is saved in `~/.kapsel/ai/config.yaml`:
```bash
kps ai config status        # View active provider and model
kps ai config test          # Test API connectivity
kps ai config model gpt-4o  # Switch active model instantly
kps ai config edit          # Edit YAML file in system editor
```

---

## License

MIT License.
