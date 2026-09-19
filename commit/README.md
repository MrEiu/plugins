# Kapsel Commit Plugin (`kps commit` / `commit`)

**Offline, rule-based Conventional Commit generator and interactive Git commit manager for Kapsel.**

100% deterministic, 0 network, 0 LLM token cost, and 0 timeouts.

---

## Features

- **Offline Git Change Deduction**: Inspects `git status` across staged and unstaged files, automatically deducing:
  - **Type**: `feat`, `fix`, `docs`, `refactor`, `perf`, `test`, `style`, `chore` based on modified files and branch context.
  - **Scope**: Inferred from active component directories (e.g. `plugins/<name>`, `kapsel/<module>`, `tests/<name>`).
  - **Subject**: Context-aware action descriptions.
- **Interactive TUI**:
  - `[Enter]` Accept & Commit directly (auto stages with `git add -A`).
  - `[e]` Edit/tweak message in place.
  - `[t]` Switch commit type with arrow-key menu.
  - `[c]` Copy to clipboard.
  - `[q / Esc]` Cancel cleanly without changes.
- **Pre-execution Interception**: Call `commit` or `kps commit` directly anywhere in Kapsel.

---

## Quick Usage

```bash
# Analyze changes, deduce message and commit interactively
commit

# Dry-run: view deduced message without executing git commit
commit -d

# Override type or scope
commit -t fix
commit -t docs -s readme

# Direct message pass-through
commit -m "feat(portal): add arrow-key navigation"
```
