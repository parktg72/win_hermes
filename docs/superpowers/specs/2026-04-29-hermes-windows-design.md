# Hermes Windows — Design Spec
**Date:** 2026-04-29
**Status:** Approved

## Overview

Fork of [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) adapted for a closed Windows intranet environment. Adds native Windows support, Ollama auto-discovery, and academic medical research project context loading. All upstream features (4-layer memory, skills system, scheduler, TUI) are inherited unchanged.

Source code is transferred to the closed machine via internal NAS or USB — no direct internet access to PyPI or GitHub from the target PC.

---

## 1. Architecture

```
NousResearch/hermes-agent (upstream remote)
        ↓ fork
this repo: hermes
├── .gitattributes              # [new] force CRLF on .bat/.cmd/.ps1
├── hermes/
│   ├── platform/
│   │   └── windows.py          # [new] Windows compatibility patches
│   └── providers/
│       └── ollama_discovery.py # [new] Ollama auto-discovery
├── vendor/
│   ├── uv.exe                  # bundled uv binary for offline install
│   └── wheels/                 # pre-downloaded .whl files (win_amd64, cp312)
├── scripts/
│   └── download_wheels.py      # run once on internet-connected PC
├── install.bat                 # single-file installer (UTF-8 + CRLF)
├── hermes.bat                  # runtime entry point (UTF-8 + CRLF)
├── pyproject.toml              # adds [windows] extra
└── AGENTS.md                   # medical research project context template
```

**`.gitattributes` (CRLF enforcement):**
```
*.bat  text eol=crlf
*.cmd  text eol=crlf
*.ps1  text eol=crlf
```

**Upstream sync strategy:** `git remote add upstream https://github.com/NousResearch/hermes-agent`. On each upstream release, `git fetch upstream` then resolve conflicts only in `windows.py` and `ollama_discovery.py`. All other files track upstream directly.

---

## 2. Installation

### Requirements
- Windows 10/11 (native, no WSL2)
- Python 3.12 (managed by uv — no pre-install required)
- Ollama installed and running on `localhost:11434`
- Repo + `vendor/` folder copied to target machine via NAS or USB

### `install.bat` flow (UTF-8 + CRLF)

```
1. Detect uv.exe in PATH — if absent, copy vendor\uv.exe to %LOCALAPPDATA%\uv\bin\
2. uv python install 3.12
3. uv venv venv --python 3.12
4. uv pip install -e ".[windows]" --find-links vendor\wheels\ --no-index
5. Verify Ollama reachability (GET localhost:11434/api/tags) — warn if not running
6. Write hermes.bat next to install.bat
7. Print usage summary
```

### `hermes.bat` (UTF-8 + CRLF)

```bat
@echo off
chcp 65001 >nul
"%~dp0venv\Scripts\python.exe" -m hermes %*
```

### Offline wheel preparation (internet-connected PC, one-time)

```bash
python scripts/download_wheels.py
# Internally runs:
# uv pip download ".[windows]" --dest vendor/wheels/ \
#   --platform win_amd64 --python-version 3.12 --only-binary=:all:
```

The `--platform win_amd64 --only-binary=:all:` flags ensure downloaded wheels are Windows-compatible even when the prep machine is macOS or Linux.

---

## 3. Windows Compatibility Layer (`hermes/platform/windows.py`)

**Upstream already handles more than expected** (confirmed by source inspection):
- `process_registry.py`: tries `winpty` first, falls back to `ptyprocess` (excluded on win32 via pyproject.toml)
- `cli.py`: SIGHUP guarded by `hasattr(_signal, 'SIGHUP')`, SIGTERM wrapped in `try/except`
- `code_execution_tool.py`: `SANDBOX_AVAILABLE = sys.platform != 'win32'`
- Python 3.12 on Windows: `asyncio.run()` already defaults to `ProactorEventLoop`

**Remaining work in `windows.py`** is therefore small:

| Item | Status | Action |
|------|--------|--------|
| asyncio ProactorEventLoop | Already default in Py 3.12 | Verify; add explicit policy as safety shim |
| pty / ConPTY | `winpty` already tried upstream | Add `winpty` to `[windows]` extra |
| ANSI colors | Not handled upstream | `colorama.init(wrap=True)` at startup |
| SIGHUP | Already conditional | No action needed |
| SIGTERM | Already try/except | No action needed |
| Path separators | Not normalized upstream | `pathlib.Path` normalization in discovery module |

Applied at process start:

```python
# hermes/__main__.py (minimal addition)
if sys.platform == "win32":
    from hermes.platform.windows import apply_windows_patches
    apply_windows_patches()
```

### Dependencies added to `[windows]` extra in `pyproject.toml`

```toml
[project.optional-dependencies]
windows = ["winpty", "colorama"]
```

---

## 4. Ollama Auto-Discovery (`hermes/providers/ollama_discovery.py`)

Runs on every `hermes` startup before the main agent loop.

```
startup
  → GET http://localhost:11434/api/tags  (timeout 2s)
  → success: parse model list
             → if config has saved model and it still exists: use it silently
             → else: show numbered selection menu → save choice to config
  → failure: print "Ollama가 실행되지 않았습니다. `ollama serve` 실행 후 재시작하세요."
             exit with code 1
```

- Last selected model persisted in `~/.hermes/config.json` under `ollama_model` key
- `hermes model` command overrides selection interactively (inherits upstream UX)
- No hardcoded model names — list always fetched live from Ollama

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

hermes-agent natively loads `AGENTS.md` at conversation start — no additional plumbing needed.

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
- Critical path test: startup → Ollama discovery (mocked) → 1 chat turn → clean exit
- Windows-specific: colorama init, path normalization, winpty import

---

## 7. Out of Scope

- macOS / Linux support changes (upstream handles these)
- Messaging gateway (Telegram, Discord) — Windows porting deferred
- Docker / SSH terminal backends — deferred
- Finetune / RL training features — not needed
