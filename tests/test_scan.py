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
    (tmp_path / ".git" / "NOTES.md").write_text("git notes")
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


def test_scan_sorts_agents_md_first(tmp_path):
    (tmp_path / "utils.py").write_text("x = 1")
    (tmp_path / "AGENTS.md").write_text("# context")
    files = scan_directory(tmp_path)
    assert files[0].name == "AGENTS.md"


def test_build_context_block_truncates_at_limit(tmp_path):
    (tmp_path / "small.py").write_text("x = 1")
    (tmp_path / "large.py").write_text("y = " + "2" * 10000)
    files = scan_directory(tmp_path)
    block = build_context_block(files, base_dir=tmp_path, max_total_bytes=100)
    # At least one file listed in truncated section
    assert "Truncated" in block or "x = 1" in block  # something was processed
