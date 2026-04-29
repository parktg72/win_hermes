# Hermes Windows Fork — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fork NousResearch/hermes-agent and add Windows-native support (colorama, winpty), Ollama auto-discovery, a single-bat installer, and medical-research project context loading.

**Architecture:** Minimal fork — pull upstream content into this repo, then add three new files (`hermes_cli/platform/windows.py`, `hermes_cli/providers/ollama_discovery.py`, `hermes_cli/scan.py`) plus installer scripts. Windows patches inject at the top of `hermes_cli/main.py:main()`. Ollama discovery runs before the chat loop starts. Directory scanning uses AGENTS.md injection with cleanup.

**Tech Stack:** Python 3.12, uv, hermes-agent v0.11.0 (upstream), Ollama HTTP API, colorama, winpty, pytest, pytest-asyncio

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `.gitattributes` | Create | Force CRLF for `.bat`/`.cmd`/`.ps1` |
| `pyproject.toml` | Modify | Python 3.12, add `[windows]` extra, bump requires-python |
| `hermes_cli/platform/__init__.py` | Create | Package marker |
| `hermes_cli/platform/windows.py` | Create | colorama init, asyncio ProactorEventLoop shim, path normalizer |
| `hermes_cli/providers/__init__.py` | Create | Package marker |
| `hermes_cli/providers/ollama_discovery.py` | Create | GET localhost:11434/api/tags → model selection → config persist |
| `hermes_cli/scan.py` | Create | Directory walker for SAS/R/Python files with token-aware truncation |
| `hermes_cli/main.py` | Modify | Inject Windows patches at top of `main()`, wire Ollama discovery into chat startup, add `init` subcommand, add `dir` arg to `chat` subparser |
| `install.bat` | Create | UTF-8+CRLF single-file installer |
| `hermes.bat` | Create | UTF-8+CRLF runtime entry point |
| `scripts/download_wheels.py` | Create | Offline wheel downloader (win_amd64, cp312) |
| `tests/test_windows.py` | Create | colorama, asyncio policy, path normalizer |
| `tests/test_ollama_discovery.py` | Create | Mock HTTP responses for discovery flow |
| `tests/test_scan.py` | Create | Directory scanner: collection, exclusion, token overflow |

---

## Task 1: Fork Setup — Pull Upstream Into This Repo

**Files:** (no new files; repo-level operation)

- [ ] **Step 1.1: Add upstream remote and fetch**

```bash
git remote add upstream https://github.com/NousResearch/hermes-agent
git fetch upstream
```

Expected: upstream/main fetched, no errors.

- [ ] **Step 1.2: Merge upstream into main (allow unrelated histories)**

Our repo has 2 commits (design docs). We merge upstream on top.

```bash
git merge upstream/main --allow-unrelated-histories -m "chore: merge upstream hermes-agent v0.11.0"
```

Expected: merge commit created. If conflict on any file we created (only `docs/` and `.claude/`), accept ours:
```bash
git checkout --ours docs/ .claude/
git add docs/ .claude/
git merge --continue
```

- [ ] **Step 1.3: Verify the merge**

```bash
python -c "import hermes_cli; print('import ok')"
# Expected: import ok   (may need: uv pip install -e . first)
ls hermes_cli/main.py pyproject.toml
```

Expected: both files present.

- [ ] **Step 1.4: Commit**

```bash
git commit --allow-empty -m "chore: record upstream baseline (hermes-agent v0.11.0)"
```

---

## Task 2: Project Scaffolding — .gitattributes + pyproject.toml

**Files:**
- Create: `.gitattributes`
- Modify: `pyproject.toml` (requires-python, [windows] extra)

- [ ] **Step 2.1: Write failing test for .gitattributes**

```python
# tests/test_gitattributes.py
from pathlib import Path

def test_bat_eol_rule_exists():
    content = Path(".gitattributes").read_text()
    assert "*.bat" in content and "eol=crlf" in content

def test_cmd_eol_rule_exists():
    content = Path(".gitattributes").read_text()
    assert "*.cmd" in content and "eol=crlf" in content

def test_ps1_eol_rule_exists():
    content = Path(".gitattributes").read_text()
    assert "*.ps1" in content and "eol=crlf" in content
```

- [ ] **Step 2.2: Run test to verify it fails**

```bash
python -m pytest tests/test_gitattributes.py -v
```

Expected: FAIL — `.gitattributes` not found or missing rules.

- [ ] **Step 2.3: Create .gitattributes**

```
# tests/test_gitattributes.py is already written above
```

Create `.gitattributes` at repo root:

```
# Enforce CRLF line endings on Windows scripts
*.bat  text eol=crlf
*.cmd  text eol=crlf
*.ps1  text eol=crlf
```

- [ ] **Step 2.4: Run test to verify it passes**

```bash
python -m pytest tests/test_gitattributes.py -v
```

Expected: PASS.

- [ ] **Step 2.5: Update pyproject.toml**

Find the line `requires-python = ">=3.11"` and change to `">=3.12"`.

Find or add after the existing `[project.optional-dependencies]` block:

```toml
[project.optional-dependencies]
# ... existing entries ...
windows = ["winpty>=0.4.3", "colorama>=0.4.6"]
```

Also update `[tool.pytest.ini_options]` to add `asyncio_mode = "auto"` if not present.

- [ ] **Step 2.6: Commit**

```bash
git add .gitattributes pyproject.toml tests/test_gitattributes.py
git commit -m "build: add .gitattributes CRLF enforcement and [windows] extra"
```

---

## Task 3: Windows Compatibility Layer

**Files:**
- Create: `hermes_cli/platform/__init__.py`
- Create: `hermes_cli/platform/windows.py`
- Create: `tests/test_windows.py`

- [ ] **Step 3.1: Write failing tests**

```python
# tests/test_windows.py
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

def test_apply_windows_patches_is_importable():
    from hermes_cli.platform.windows import apply_windows_patches
    assert callable(apply_windows_patches)

def test_normalize_path_converts_backslashes():
    from hermes_cli.platform.windows import normalize_path
    result = normalize_path(r"C:\Users\test\project")
    assert "\\" not in result

def test_normalize_path_accepts_forward_slashes():
    from hermes_cli.platform.windows import normalize_path
    result = normalize_path("C:/Users/test/project")
    assert result == "C:/Users/test/project"

def test_apply_windows_patches_calls_colorama_init():
    with patch("hermes_cli.platform.windows.colorama") as mock_colorama:
        from hermes_cli.platform.windows import apply_windows_patches
        apply_windows_patches()
        mock_colorama.init.assert_called_once_with(wrap=True)

def test_apply_windows_patches_sets_proactor_policy():
    with patch("hermes_cli.platform.windows.asyncio") as mock_asyncio:
        mock_policy = MagicMock()
        mock_asyncio.WindowsProactorEventLoopPolicy.return_value = mock_policy
        from hermes_cli.platform.windows import apply_windows_patches
        apply_windows_patches()
        mock_asyncio.set_event_loop_policy.assert_called_once_with(mock_policy)
```

- [ ] **Step 3.2: Run tests to verify they fail**

```bash
python -m pytest tests/test_windows.py -v
```

Expected: FAIL — `hermes_cli.platform.windows` not found.

- [ ] **Step 3.3: Create package markers**

```python
# hermes_cli/platform/__init__.py
```

(empty file)

- [ ] **Step 3.4: Create hermes_cli/platform/windows.py**

```python
import asyncio
import sys
from pathlib import Path


def _import_colorama():
    try:
        import colorama
        return colorama
    except ImportError:
        return None


colorama = _import_colorama()


def apply_windows_patches() -> None:
    """Inject Windows-specific compatibility patches. Call once at process start."""
    if colorama is not None:
        colorama.init(wrap=True)

    # Python 3.12 already defaults to ProactorEventLoop on Windows,
    # but we set it explicitly as a safety shim against edge cases.
    if hasattr(asyncio, "WindowsProactorEventLoopPolicy"):
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


def normalize_path(path: str) -> str:
    """Return path with backslashes replaced by forward slashes."""
    return str(Path(path).as_posix())
```

- [ ] **Step 3.5: Run tests to verify they pass**

```bash
python -m pytest tests/test_windows.py -v
```

Expected: PASS (all 5 tests).

- [ ] **Step 3.6: Commit**

```bash
git add hermes_cli/platform/ tests/test_windows.py
git commit -m "feat: add Windows compatibility layer (colorama, ProactorEventLoop)"
```

---

## Task 4: Ollama Auto-Discovery

**Files:**
- Create: `hermes_cli/providers/__init__.py`
- Create: `hermes_cli/providers/ollama_discovery.py`
- Create: `tests/test_ollama_discovery.py`

- [ ] **Step 4.1: Write failing tests**

```python
# tests/test_ollama_discovery.py
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from hermes_cli.providers.ollama_discovery import (
    fetch_ollama_models,
    select_model,
    OllamaNotRunningError,
)


@pytest.mark.asyncio
async def test_fetch_ollama_models_returns_list():
    fake_response = {"models": [{"name": "llama3.2:latest"}, {"name": "mistral:7b"}]}
    mock_resp = AsyncMock()
    mock_resp.json = AsyncMock(return_value=fake_response)
    mock_resp.raise_for_status = MagicMock()

    with patch("hermes_cli.providers.ollama_discovery.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__ = AsyncMock(return_value=MagicMock(
            get=AsyncMock(return_value=mock_resp)
        ))
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
        models = await fetch_ollama_models()

    assert models == ["llama3.2:latest", "mistral:7b"]


@pytest.mark.asyncio
async def test_fetch_ollama_models_raises_when_not_running():
    import httpx
    with patch("hermes_cli.providers.ollama_discovery.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__ = AsyncMock(side_effect=httpx.ConnectError("refused"))
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
        with pytest.raises(OllamaNotRunningError):
            await fetch_ollama_models()


def test_select_model_returns_saved_when_valid():
    models = ["llama3.2:latest", "mistral:7b"]
    result = select_model(models, saved="llama3.2:latest")
    assert result == "llama3.2:latest"


def test_select_model_ignores_stale_saved():
    models = ["mistral:7b"]
    # saved model no longer exists in Ollama
    result = select_model(models, saved="llama3.2:latest", auto_pick_first=True)
    assert result == "mistral:7b"


def test_select_model_raises_on_empty_list():
    with pytest.raises(ValueError, match="No models"):
        select_model([], saved=None)
```

- [ ] **Step 4.2: Run tests to verify they fail**

```bash
python -m pytest tests/test_ollama_discovery.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 4.3: Create package marker**

```python
# hermes_cli/providers/__init__.py
```

(empty file)

- [ ] **Step 4.4: Create hermes_cli/providers/ollama_discovery.py**

```python
"""Discover and select Ollama models running on localhost."""
from __future__ import annotations

import sys
from typing import Optional

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore[assignment]

OLLAMA_BASE = "http://localhost:11434"
TIMEOUT = 2.0


class OllamaNotRunningError(RuntimeError):
    """Raised when Ollama is not reachable on localhost:11434."""


async def fetch_ollama_models() -> list[str]:
    """Return list of model names from running Ollama instance.

    Raises:
        OllamaNotRunningError: if Ollama is not reachable.
    """
    if httpx is None:
        raise ImportError("httpx is required for Ollama discovery")

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(f"{OLLAMA_BASE}/api/tags")
            resp.raise_for_status()
            data = resp.json()
            return [m["name"] for m in data.get("models", [])]
    except (httpx.ConnectError, httpx.ConnectTimeout, httpx.TimeoutException) as exc:
        raise OllamaNotRunningError(
            "Ollama가 실행되지 않았습니다. `ollama serve` 실행 후 재시작하세요."
        ) from exc


def select_model(
    models: list[str],
    saved: Optional[str],
    *,
    auto_pick_first: bool = False,
) -> str:
    """Return the model to use, prompting if needed.

    Args:
        models: Available model names from Ollama.
        saved: Last-used model name from config (may be None or stale).
        auto_pick_first: If True, skip interactive prompt (for tests).

    Returns:
        Selected model name.

    Raises:
        ValueError: If models list is empty.
    """
    if not models:
        raise ValueError("No models found in Ollama. Run `ollama pull <model>` first.")

    if saved and saved in models:
        return saved

    if auto_pick_first or not sys.stdin.isatty():
        return models[0]

    print("\nOllama 모델을 선택하세요:")
    for i, name in enumerate(models, 1):
        print(f"  {i}. {name}")

    while True:
        try:
            choice = input(f"번호 입력 [1-{len(models)}]: ").strip()
            idx = int(choice) - 1
            if 0 <= idx < len(models):
                return models[idx]
        except (ValueError, EOFError):
            pass
        print(f"1에서 {len(models)} 사이의 번호를 입력하세요.")
```

- [ ] **Step 4.5: Run tests to verify they pass**

```bash
python -m pytest tests/test_ollama_discovery.py -v
```

Expected: PASS (all 5 tests).

- [ ] **Step 4.6: Commit**

```bash
git add hermes_cli/providers/ tests/test_ollama_discovery.py
git commit -m "feat: add Ollama auto-discovery with model selection"
```

---

## Task 5: Directory Scanner

**Files:**
- Create: `hermes_cli/scan.py`
- Create: `tests/test_scan.py`

- [ ] **Step 5.1: Write failing tests**

```python
# tests/test_scan.py
import os
import tempfile
from pathlib import Path

import pytest

from hermes_cli.scan import scan_directory, build_context_block, COLLECTED_EXTENSIONS


def _make_project(tmp_path: Path) -> Path:
    (tmp_path / "analysis.sas").write_text("proc means data=nhis; run;")
    (tmp_path / "model.R").write_text("library(tidyverse)")
    (tmp_path / "utils.py").write_text("def clean(df): return df")
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "junk.pyc").write_text("bytecode")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("[core]")
    return tmp_path


def test_scan_collects_target_extensions(tmp_path):
    _make_project(tmp_path)
    files = scan_directory(tmp_path)
    names = [f.name for f in files]
    assert "analysis.sas" in names
    assert "model.R" in names
    assert "utils.py" in names


def test_scan_excludes_pycache(tmp_path):
    _make_project(tmp_path)
    files = scan_directory(tmp_path)
    paths = [str(f) for f in files]
    assert not any("__pycache__" in p for p in paths)


def test_scan_excludes_git(tmp_path):
    _make_project(tmp_path)
    files = scan_directory(tmp_path)
    paths = [str(f) for f in files]
    assert not any(".git" in p for p in paths)


def test_scan_excludes_large_files(tmp_path):
    big = tmp_path / "big.py"
    big.write_bytes(b"x" * (101 * 1024))  # 101 KB
    files = scan_directory(tmp_path)
    assert big not in files


def test_build_context_block_contains_file_contents(tmp_path):
    _make_project(tmp_path)
    files = scan_directory(tmp_path)
    block = build_context_block(files, base_dir=tmp_path)
    assert "proc means" in block
    assert "library(tidyverse)" in block
    assert "def clean" in block


def test_collected_extensions_includes_sas_and_r():
    assert ".sas" in COLLECTED_EXTENSIONS
    assert ".R" in COLLECTED_EXTENSIONS
    assert ".py" in COLLECTED_EXTENSIONS
```

- [ ] **Step 5.2: Run tests to verify they fail**

```bash
python -m pytest tests/test_scan.py -v
```

Expected: FAIL — `hermes_cli.scan` not found.

- [ ] **Step 5.3: Create hermes_cli/scan.py**

```python
"""Directory scanner for project context loading."""
from __future__ import annotations

from pathlib import Path
from typing import Sequence

COLLECTED_EXTENSIONS = frozenset({
    ".sas", ".R", ".Rmd", ".py", ".sql", ".do", ".md", ".txt", ".csv",
})

EXCLUDED_DIRS = frozenset({
    ".git", "__pycache__", "venv", ".venv", "renv", "node_modules",
    ".tox", "dist", "build", ".mypy_cache", ".ruff_cache",
})

MAX_FILE_BYTES = 100 * 1024  # 100 KB


def scan_directory(root: Path) -> list[Path]:
    """Return source files under root matching COLLECTED_EXTENSIONS.

    Files are sorted: AGENTS.md/CLAUDE.md first, then by mtime desc,
    then by size asc — so token-overflow truncation drops large old files first.
    """
    root = Path(root).resolve()
    collected: list[Path] = []

    for path in root.rglob("*"):
        if path.is_dir():
            continue
        if any(part in EXCLUDED_DIRS for part in path.parts):
            continue
        if path.suffix not in COLLECTED_EXTENSIONS:
            continue
        if path.stat().st_size > MAX_FILE_BYTES:
            continue
        collected.append(path)

    def sort_key(p: Path) -> tuple:
        priority = 0 if p.name in ("AGENTS.md", "CLAUDE.md") else 1
        return (priority, -p.stat().st_mtime, p.stat().st_size)

    return sorted(collected, key=sort_key)


def build_context_block(files: Sequence[Path], base_dir: Path) -> str:
    """Return a markdown block embedding all file contents."""
    parts: list[str] = ["# Project Files\n"]
    for f in files:
        try:
            rel = f.relative_to(base_dir)
        except ValueError:
            rel = f
        content = f.read_text(encoding="utf-8", errors="replace")
        parts.append(f"\n## {rel}\n\n```\n{content}\n```\n")
    return "".join(parts)
```

- [ ] **Step 5.4: Run tests to verify they pass**

```bash
python -m pytest tests/test_scan.py -v
```

Expected: PASS (all 6 tests).

- [ ] **Step 5.5: Commit**

```bash
git add hermes_cli/scan.py tests/test_scan.py
git commit -m "feat: add directory scanner for project context loading"
```

---

## Task 6: Wire Into main() — Windows Patches + Ollama + hermes init + hermes chat \<dir\>

**Files:**
- Modify: `hermes_cli/main.py`

**Context:** `main()` is at line 7751 of `hermes_cli/main.py`. The `chat` subparser is created inside `main()`.

- [ ] **Step 6.1: Inject Windows patches at top of main()**

Find the start of `def main():` in `hermes_cli/main.py`. Add immediately after the docstring, before any other code:

```python
def main():
    """Main entry point for hermes CLI."""
    # Windows compatibility — must run before any asyncio or terminal setup
    if __import__("sys").platform == "win32":
        from hermes_cli.platform.windows import apply_windows_patches
        apply_windows_patches()

    parser = argparse.ArgumentParser(  # existing line, unchanged
```

- [ ] **Step 6.2: Add `hermes init` subcommand**

Find where subparsers are created in `main()` (look for `subparsers = parser.add_subparsers`). Add after the existing subparsers:

```python
    # hermes init — create AGENTS.md in current directory
    init_parser = subparsers.add_parser(
        "init",
        help="Create AGENTS.md project context in current directory",
    )
    init_parser.set_defaults(subcommand="init")
```

At the bottom of `main()`, find where subcommands are dispatched (look for `if args.subcommand == "..."`). Add:

```python
    elif getattr(args, "subcommand", None) == "init":
        _cmd_init()
        return
```

Add this function anywhere before `main()`:

```python
_AGENTS_MD_TEMPLATE = """\
# Project Context
Language: SAS / R / Python
Domain: Academic medical research (NHIS cohort / NMA)
Correctness priority: numbers before interpretation before caveat
ICD codes and variable names: never invent — ask if uncertain
Output directory: /out/<date>/
"""

def _cmd_init() -> None:
    """Create AGENTS.md in the current directory."""
    target = Path.cwd() / "AGENTS.md"
    if target.exists():
        print(f"AGENTS.md already exists at {target}. Skipping.")
        return
    target.write_text(_AGENTS_MD_TEMPLATE, encoding="utf-8")
    print(f"Created {target}")
    print("Run `hermes` in this directory to start a project-aware session.")
```

- [ ] **Step 6.3: Add `dir` argument to `hermes chat` subparser and wire directory scanning**

Find where the `chat` subparser is created (search for `"chat"` near `add_parser`). Add after existing chat arguments:

```python
    chat_parser.add_argument(
        "dir",
        nargs="?",
        default=None,
        metavar="DIR",
        help="Load all source files from DIR as project context before chatting",
    )
```

Find where the chat subcommand is handled (look for `args.subcommand == "chat"` or equivalent). Before the existing chat launch, inject:

```python
    if getattr(args, "dir", None):
        _inject_dir_context(Path(args.dir))
```

Add this function before `main()`:

```python
def _inject_dir_context(project_dir: Path) -> None:
    """Scan project_dir and inject file contents into AGENTS.md for the session.

    Creates a temporary section at the bottom of AGENTS.md (or creates it).
    Registers an atexit handler to remove the injected section on exit.
    """
    import atexit
    import os
    from hermes_cli.scan import scan_directory, build_context_block

    project_dir = project_dir.resolve()
    if not project_dir.is_dir():
        print(f"Warning: {project_dir} is not a directory. Ignoring.", file=__import__("sys").stderr)
        return

    agents_md = project_dir / "AGENTS.md"
    marker_start = "<!-- hermes-scan-start -->\n"
    marker_end = "<!-- hermes-scan-end -->\n"

    files = scan_directory(project_dir)
    if not files:
        print(f"No source files found in {project_dir}.")
        return

    context_block = build_context_block(files, base_dir=project_dir)
    injected_section = f"\n{marker_start}{context_block}\n{marker_end}"

    original_content: str | None = None
    if agents_md.exists():
        original_content = agents_md.read_text(encoding="utf-8")
        if marker_start in original_content:
            # Already injected (e.g., crash recovery); leave as-is
            pass
        else:
            agents_md.write_text(original_content + injected_section, encoding="utf-8")
    else:
        agents_md.write_text(injected_section, encoding="utf-8")

    os.chdir(project_dir)
    print(f"Loaded {len(files)} file(s) from {project_dir} as context.")

    def _cleanup():
        if agents_md.exists():
            text = agents_md.read_text(encoding="utf-8")
            start_idx = text.find(marker_start)
            if start_idx != -1:
                cleaned = text[:start_idx]
                if cleaned.strip():
                    agents_md.write_text(cleaned, encoding="utf-8")
                else:
                    agents_md.unlink()

    atexit.register(_cleanup)
```

- [ ] **Step 6.4: Verify the additions parse without error**

```bash
python -c "from hermes_cli.main import main; print('main() importable')"
python -m hermes --help 2>&1 | grep -E "init|chat"
```

Expected: `main() importable` and `init` + `chat` appear in help output.

- [ ] **Step 6.5: Commit**

```bash
git add hermes_cli/main.py
git commit -m "feat: wire Windows patches, Ollama discovery, hermes init, and chat --dir into main()"
```

---

## Task 7: install.bat + hermes.bat

**Files:**
- Create: `install.bat` (UTF-8 + CRLF)
- Create: `hermes.bat` (UTF-8 + CRLF)

> **Note for macOS implementer:** Create these files, then convert to CRLF before committing. `unix2dos install.bat hermes.bat` or use Python: `open('install.bat','rb+').write(open('install.bat','rb').read().replace(b'\n',b'\r\n'))`. The `.gitattributes` rule will enforce CRLF when cloned on Windows.

- [ ] **Step 7.1: Create hermes.bat**

```bat
@echo off
chcp 65001 >nul
"%~dp0venv\Scripts\python.exe" -m hermes_cli.main %*
```

Save as `hermes.bat`. Then convert line endings:

```bash
python3 -c "
p='hermes.bat'
open(p,'wb').write(open(p,'rb').read().replace(b'\r\n',b'\n').replace(b'\n',b'\r\n'))
print('CRLF applied to', p)
"
```

- [ ] **Step 7.2: Create install.bat**

```bat
@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

echo === Hermes Windows Installer ===
echo.

:: Step 1: Ensure uv is available
where uv >nul 2>&1
if %ERRORLEVEL% neq 0 (
    if exist "%~dp0vendor\uv.exe" (
        echo uv를 설치합니다...
        copy "%~dp0vendor\uv.exe" "%LOCALAPPDATA%\uv\bin\uv.exe" >nul 2>&1
        set "PATH=%LOCALAPPDATA%\uv\bin;%PATH%"
    ) else (
        echo [오류] uv.exe를 찾을 수 없습니다.
        echo vendor\uv.exe 파일이 있는지 확인하세요.
        pause
        exit /b 1
    )
)
echo [1/5] uv 확인 완료

:: Step 2: Create venv with Python 3.12
echo [2/5] Python 3.12 가상환경 생성 중...
uv python install 3.12 --quiet
uv venv "%~dp0venv" --python 3.12 --quiet
if %ERRORLEVEL% neq 0 (
    echo [오류] 가상환경 생성 실패
    pause
    exit /b 1
)

:: Step 3: Install packages from vendor/wheels (offline)
echo [3/5] 패키지 설치 중 (오프라인)...
if exist "%~dp0vendor\wheels" (
    "%~dp0venv\Scripts\python.exe" -m pip install --quiet ^
        --no-index --find-links "%~dp0vendor\wheels" ^
        -e "%~dp0.[windows]"
) else (
    echo [경고] vendor\wheels 폴더 없음. 온라인 설치 시도...
    "%~dp0venv\Scripts\python.exe" -m pip install --quiet -e "%~dp0.[windows]"
)
if %ERRORLEVEL% neq 0 (
    echo [오류] 패키지 설치 실패
    pause
    exit /b 1
)

:: Step 4: Check Ollama
echo [4/5] Ollama 연결 확인 중...
curl -s --max-time 2 http://localhost:11434/api/tags >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [경고] Ollama가 실행되지 않았습니다.
    echo        설치 후 ollama serve 를 실행하고 hermes.bat를 시작하세요.
) else (
    echo [4/5] Ollama 연결 확인 완료
)

:: Step 5: Confirm hermes.bat exists
echo [5/5] 설치 완료
echo.
echo 사용법:
echo   hermes.bat              대화 시작
echo   hermes.bat init         프로젝트 컨텍스트 초기화
echo   hermes.bat chat .\src   디렉토리 컨텍스트로 대화 시작
echo.
pause
```

Save as `install.bat`. Then convert line endings:

```bash
python3 -c "
p='install.bat'
open(p,'wb').write(open(p,'rb').read().replace(b'\r\n',b'\n').replace(b'\n',b'\r\n'))
print('CRLF applied to', p)
"
```

- [ ] **Step 7.3: Verify CRLF**

```bash
python3 -c "
for f in ['install.bat','hermes.bat']:
    raw = open(f,'rb').read()
    crlf = raw.count(b'\r\n')
    lf_only = raw.count(b'\n') - crlf
    print(f'{f}: CRLF={crlf} LF-only={lf_only}')
"
```

Expected: `LF-only=0` for both files.

- [ ] **Step 7.4: Commit**

```bash
git add install.bat hermes.bat
git commit -m "feat: add install.bat and hermes.bat (UTF-8+CRLF)"
```

---

## Task 8: Offline Wheel Downloader

**Files:**
- Create: `scripts/download_wheels.py`

- [ ] **Step 8.1: Create scripts/download_wheels.py**

```python
#!/usr/bin/env python3
"""Download Windows wheels for offline installation.

Run this script ONCE on an internet-connected machine (any OS):

    python scripts/download_wheels.py

It downloads win_amd64 / cp312 wheels into vendor/wheels/.
Copy the vendor/ directory to the target Windows machine.
"""
import subprocess
import sys
from pathlib import Path

VENDOR_WHEELS = Path(__file__).parent.parent / "vendor" / "wheels"

def main() -> None:
    VENDOR_WHEELS.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable, "-m", "pip", "download",
        ".[windows]",
        "--dest", str(VENDOR_WHEELS),
        "--platform", "win_amd64",
        "--python-version", "3.12",
        "--only-binary", ":all:",
        "--quiet",
    ]
    print(f"Downloading wheels to {VENDOR_WHEELS} ...")
    print("Command:", " ".join(cmd))
    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        print("\n[오류] 일부 패키지를 다운로드하지 못했습니다.")
        print("pip 버전을 업그레이드하거나 --only-binary 없이 재시도하세요.")
        sys.exit(1)
    wheels = list(VENDOR_WHEELS.glob("*.whl"))
    print(f"\n완료: {len(wheels)}개 wheel 파일 저장됨 → {VENDOR_WHEELS}")

if __name__ == "__main__":
    main()
```

- [ ] **Step 8.2: Verify the script is syntactically valid**

```bash
python3 -m py_compile scripts/download_wheels.py && echo "syntax ok"
```

Expected: `syntax ok`.

- [ ] **Step 8.3: Add vendor/wheels to .gitignore**

Append to `.gitignore` (create if it doesn't exist):

```
vendor/wheels/
vendor/uv.exe
```

- [ ] **Step 8.4: Commit**

```bash
git add scripts/download_wheels.py .gitignore
git commit -m "build: add offline wheel downloader and gitignore vendor binaries"
```

---

## Task 9: Full Test Suite Run and CI Configuration

**Files:**
- Modify: `pyproject.toml` (ensure test config correct)

- [ ] **Step 9.1: Run the full test suite**

```bash
python -m pytest tests/test_gitattributes.py tests/test_windows.py tests/test_ollama_discovery.py tests/test_scan.py -v
```

Expected: All tests PASS. Note the total count and any skips.

- [ ] **Step 9.2: Fix any failures before continuing**

If failures exist, fix the underlying code — do not skip tests. Common issues:
- Missing `httpx` dependency: `uv pip install httpx`
- Missing `pytest-asyncio`: `uv pip install pytest-asyncio`
- Import errors: check `hermes_cli/providers/__init__.py` exists

- [ ] **Step 9.3: Run upstream tests to check for regressions**

```bash
python -m pytest tests/ -v --ignore=tests/test_gitattributes.py -x -q 2>&1 | tail -30
```

Expected: upstream tests pass or skip (some may require network/API keys and skip gracefully).

- [ ] **Step 9.4: Commit final state**

```bash
git add -p   # review any remaining changes
git commit -m "test: verify full test suite passes on upstream + new Windows/Ollama/scan tests"
```

---

## Self-Review Checklist

Spec requirement → task mapping:

| Spec Requirement | Task |
|-----------------|------|
| `.gitattributes` CRLF enforcement | Task 2 |
| Python 3.12 | Task 2 |
| `[windows]` extra in pyproject.toml | Task 2 |
| `hermes_cli/platform/windows.py` colorama + ProactorEventLoop | Task 3 |
| `hermes_cli/providers/ollama_discovery.py` | Task 4 |
| Windows patches injected at main() start | Task 6 |
| Ollama model selection + config persist | Task 4 + Task 6 |
| `hermes init` subcommand → creates AGENTS.md | Task 6 |
| `hermes chat <dir>` → directory scan + context inject | Task 5 + Task 6 |
| `install.bat` UTF-8+CRLF single-file installer | Task 7 |
| `hermes.bat` UTF-8+CRLF entry point | Task 7 |
| `scripts/download_wheels.py` with `--platform win_amd64` | Task 8 |
| Fork upstream + upstream sync strategy | Task 1 |
| `vendor/wheels/` gitignored | Task 8 |

**Ollama config persist gap:** Task 4 defines `select_model()` but does not show where the selection is saved to `~/.hermes/config.json`. Add this to Task 6 Step 6.3 implementation: after calling `select_model()`, write the result to `Path.home() / ".hermes" / "config.json"` under key `"ollama_model"`. Read it back at next startup via `json.loads(config_path.read_text()).get("ollama_model")`. The implementer should add this in the `_inject_dir_context` wiring step.
