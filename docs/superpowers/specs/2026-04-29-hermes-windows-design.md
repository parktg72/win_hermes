# Hermes Windows — Design Spec
**Date:** 2026-04-29
**Status:** Approved

## Overview

Fork of [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) adapted for a closed Windows intranet environment. Adds native Windows support, Ollama auto-discovery, and academic medical research project context loading. All upstream features (4-layer memory, skills system, scheduler, TUI) are inherited unchanged.

---

## 1. Architecture

```
NousResearch/hermes-agent (upstream remote)
        ↓ fork
this repo: hermes
├── hermes/
│   ├── platform/
│   │   └── windows.py          # [new] Windows compatibility patches
│   └── providers/
│       └── ollama_discovery.py # [new] Ollama auto-discovery
├── vendor/
│   ├── uv.exe                  # bundled for offline install
│   └── wheels/                 # pre-downloaded .whl files
├── scripts/
│   └── download_wheels.py      # run once on internet-connected PC
├── install.bat                 # single-file installer (UTF-8 + CRLF)
├── hermes.bat                  # runtime entry point (UTF-8 + CRLF)
├── pyproject.toml              # adds [windows] extra
└── AGENTS.md                   # medical research project context template
```

**Upstream sync strategy:** `git remote add upstream https://github.com/NousResearch/hermes-agent`. On each upstream release, `git fetch upstream` then resolve conflicts only in `windows.py` and `ollama_discovery.py`. All other files track upstream directly.

---

## 2. Installation

### Requirements
- Windows 10/11 (native, no WSL2)
- Python 3.12 (bundled via uv or pre-installed)
- Ollama running on `localhost:11434` before first launch

### `install.bat` flow (UTF-8 + CRLF)

```
1. Detect uv.exe — if absent, copy from vendor/uv.exe to %LOCALAPPDATA%\uv\
2. uv python install 3.12
3. uv venv venv --python 3.12
4. uv pip install -e ".[windows]" --find-links vendor\wheels\ (offline)
5. Verify Ollama reachability — warn if not running
6. Write hermes.bat next to install.bat
7. Print usage summary
```

### `hermes.bat` (UTF-8 + CRLF)

```bat
@echo off
chcp 65001 >nul
"%~dp0venv\Scripts\python.exe" -m hermes %*
```

### Offline wheel preparation (internet PC, one-time)

```
python scripts/download_wheels.py
  → uv pip download ".[windows]" --dest vendor/wheels/
```

---

## 3. Windows Compatibility Layer (`hermes/platform/windows.py`)

Applied at process start via conditional import in `hermes/__main__.py`:

```python
if sys.platform == "win32":
    from hermes.platform.windows import apply_windows_patches
    apply_windows_patches()
```

| Problem | Root cause | Fix |
|---------|-----------|-----|
| asyncio errors | `SelectorEventLoop` default | `asyncio.set_event_loop_policy(WindowsProactorEventLoopPolicy())` |
| Terminal raw mode / pty | `os.openpty()` Unix-only | `pywinpty` (ConPTY wrapper) |
| ANSI color broken | CMD default off | `colorama.init(wrap=True)` + Windows Terminal detection |
| SIGTERM missing | Not implemented on Windows | Replace with `CTRL_C_EVENT` handler |
| Path separators | Backslash/slash mixing | Normalize all paths via `pathlib.Path` |

### Dependencies added to `[windows]` extra in `pyproject.toml`

```toml
[project.optional-dependencies]
windows = ["pywinpty", "colorama", "pywin32"]
```

---

## 4. Ollama Auto-Discovery (`hermes/providers/ollama_discovery.py`)

Runs on every `hermes` startup before the main agent loop.

```
startup
  → GET http://localhost:11434/api/tags  (timeout 2s)
  → success: parse model list → show selection menu → remember choice in config
  → failure: print "Ollama가 실행되지 않았습니다. `ollama serve` 실행 후 재시작하세요."
             exit with code 1
```

- Last selected model persisted in `~/.hermes/config.json` (`ollama_model` key)
- `hermes model` command overrides selection (inherits upstream UX)
- No hardcoded model names — list is always fetched live from Ollama

---

## 5. Project Context Loading

### `hermes init` (new subcommand)

Creates `AGENTS.md` in the current directory:

```markdown
# Project Context
Language: SAS / R / Python
Domain: Academic medical research (NHIS cohort / NMA)
Correctness priority: numbers before interpretation before caveat
ICD codes and variable names: never invent — ask if uncertain
Output directory: /out/<date>/
```

### `hermes chat <dir>` — directory scan

**Collected:** `.sas` `.R` `.Rmd` `.py` `.sql` `.do` `.md` `.txt` `.csv` (≤ 100 KB each)

**Excluded:** `.git/` `__pycache__/` `venv/` `renv/` `*.lock` `*.rdb` `*.RData`

**Token overflow priority (truncate from lowest):**
1. `AGENTS.md` / `CLAUDE.md` — always included
2. Recently modified files
3. Remaining files sorted by size ascending

### Dynamic context addition (inherited from upstream)

```
/add ./analysis/nhis_cohort.sas   # add single file mid-conversation
/add ./src/                       # add directory
```

---

## 6. Testing Strategy

- `pytest` + `pytest-asyncio`
- GitHub Actions matrix: `windows-latest` + `ubuntu-latest`
- Critical path test: startup → Ollama discovery → 1 chat turn → clean exit
- Windows-specific: asyncio policy, path normalization, ConPTY terminal init

---

## 7. Out of Scope

- macOS / Linux support changes (upstream handles these)
- Messaging gateway (Telegram, Discord) — Windows porting deferred
- Docker / SSH terminal backends — deferred
- Finetune / RL training features — not needed
