"""Lightweight tests for scripts/download_uv.py.

Network-free: only exercises pure-helper logic and verifies that the
gitignore + sidecar marker plumbing matches the script's assumptions.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "download_uv.py"


def _load() -> object:
    spec = importlib.util.spec_from_file_location("download_uv", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["download_uv"] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def test_script_imports_cleanly():
    mod = _load()
    assert hasattr(mod, "main")
    assert hasattr(mod, "DEFAULT_UV_VERSION")
    assert hasattr(mod, "ZIP_URL")
    assert hasattr(mod, "SHA_URL")
    assert hasattr(mod, "TARGET_EXE")


def test_default_uv_version_looks_like_semver():
    mod = _load()
    parts = mod.DEFAULT_UV_VERSION.split(".")
    assert len(parts) >= 2
    assert all(p.isdigit() for p in parts), mod.DEFAULT_UV_VERSION


def test_target_path_under_vendor():
    mod = _load()
    assert mod.TARGET_EXE.name == "uv.exe"
    assert mod.TARGET_EXE.parent.name == "vendor"


def test_zip_url_points_at_official_release():
    mod = _load()
    assert mod.ZIP_URL.startswith("https://github.com/astral-sh/uv/releases/download/")
    assert mod.ZIP_URL.endswith("uv-x86_64-pc-windows-msvc.zip")
    assert mod.SHA_URL == mod.ZIP_URL + ".sha256"


def test_sha256_parser_accepts_two_column_form():
    mod = _load()
    sample = "deadbeef" * 8 + "  uv-x86_64-pc-windows-msvc.zip\n"
    assert mod._parse_sha256_line(sample) == "deadbeef" * 8


def test_sha256_parser_accepts_bare_hash_line():
    mod = _load()
    sample = "AB" * 32 + "\n"
    assert mod._parse_sha256_line(sample) == ("ab" * 32)


def test_sha256_parser_rejects_garbage():
    mod = _load()
    with pytest.raises(SystemExit):
        mod._parse_sha256_line("not a hash\n")


def test_gitignore_excludes_uv_artifacts():
    body = (REPO_ROOT / ".gitignore").read_text()
    for entry in ("vendor/uv.exe", "vendor/uv.exe.sha256", "vendor/wheels/"):
        assert entry in body, f"missing {entry} in .gitignore"


def test_download_wheels_bat_invokes_download_uv():
    """download_wheels.bat must call download_uv.py before download_wheels.py
    so the closed-network operator gets both artifacts in one click."""
    bat = (REPO_ROOT / "download_wheels.bat").read_bytes()
    assert b"scripts\\download_uv.py" in bat
    assert b"scripts\\download_wheels.py" in bat
    # uv.exe step must come before wheels step
    assert bat.index(b"download_uv.py") < bat.index(b"download_wheels.py")


def test_download_wheels_includes_build_backend():
    script = (REPO_ROOT / "scripts" / "download_wheels.py").read_text()
    assert "setuptools>=61.0" in script
    assert '"setuptools"' in script


def test_install_bat_uses_offline_build_backend_before_editable_install():
    bat = (REPO_ROOT / "install.bat").read_text(encoding="utf-8")
    assert "setuptools-*.whl" in bat
    assert '"setuptools>=61.0"' in bat
    assert "--no-build-isolation" in bat
    assert '-e ".[windows]"' in bat
