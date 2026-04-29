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
