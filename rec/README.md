# Rec Plugin for Kapsel

Command snippet recording and search execution plugin for the **Kapsel** shell, powered by the [pet](https://github.com/knqyf263/pet) CLI snippet manager.

## Installation

Add and enable the plugin via Kapsel system command:

```bash
kapsel add rec
```
*(Automatically ensures the official `pet` standalone binary is installed).*

## Usage

### 1. Record / Create Snippets (`kps rec new`)
Create a new snippet interactively:
```bash
kps rec new
```
Or record a command directly:
```bash
kps rec new docker run -d -p 80:80 nginx
```

### 2. Search & Execute Snippets (`kps rec`)
Search saved snippets interactively and execute the selected one:
```bash
# Interactive fuzzy search & run
kps rec

# Search with initial query and run
kps rec docker
```

### 3. Additional Commands
* **List snippets**: `kps rec list`
* **Search snippets only**: `kps rec search <query>`
* **Edit snippets configuration**: `kps rec edit`
* **Sync snippets with Gist/GitLab**: `kps rec sync`

## License
MIT License.
