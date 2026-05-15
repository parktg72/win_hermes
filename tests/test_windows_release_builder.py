from __future__ import annotations

import importlib.util
import sys
import zipfile
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "build_windows_release.py"


def _load():
    spec = importlib.util.spec_from_file_location("build_windows_release", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["build_windows_release"] = mod
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _write_crlf(path: Path, text: str) -> None:
    path.write_bytes(text.replace("\n", "\r\n").encode("utf-8"))


def _make_release_tree(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    for name in (
        "pyproject.toml",
        "README.md",
        "README-KO.md",
        "LICENSE",
    ):
        (root / name).write_text("x\n", encoding="utf-8")
    _write_crlf(root / "install.bat", "@echo off\nexit /b 0\n")
    _write_crlf(root / "hermes.bat", "@echo off\nexit /b %ERRORLEVEL%\n")
    _write_crlf(root / "download_wheels.bat", "@echo off\nexit /b 0\n")
    for dirname in ("hermes_cli", "agent", "tools", "scripts"):
        (root / dirname).mkdir()
        (root / dirname / "__init__.py").write_text("", encoding="utf-8")
    vendor = root / "vendor"
    wheels = vendor / "wheels"
    wheels.mkdir(parents=True)
    (vendor / "uv.exe").write_bytes(b"uv")
    (wheels / "setuptools-1-py3-none-any.whl").write_bytes(b"wheel")
    return root


def test_validate_release_tree_accepts_required_artifacts(tmp_path):
    mod = _load()
    root = _make_release_tree(tmp_path)

    result = mod.validate_release_tree(root)

    assert result.ok is True
    assert result.errors == []


def test_validate_release_tree_rejects_lf_bat(tmp_path):
    mod = _load()
    root = _make_release_tree(tmp_path)
    (root / "install.bat").write_text("@echo off\n", encoding="utf-8")

    result = mod.validate_release_tree(root)

    assert result.ok is False
    assert any("install.bat" in err and "CRLF" in err for err in result.errors)


def test_build_release_zip_places_vendor_under_prefix(tmp_path):
    mod = _load()
    root = _make_release_tree(tmp_path)
    out_dir = tmp_path / "dist"

    zip_path = mod.build_release_zip(root, "v0.11.0-win.test", out_dir)

    assert zip_path.exists()
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
    prefix = "win_hermes-v0.11.0-win.test/"
    assert all(name.startswith(prefix) for name in names)
    assert prefix + "vendor/uv.exe" in names
    assert prefix + "vendor/wheels/setuptools-1-py3-none-any.whl" in names


def test_check_only_exits_nonzero_when_vendor_missing(tmp_path):
    mod = _load()
    root = _make_release_tree(tmp_path)
    (root / "vendor" / "uv.exe").unlink()

    with pytest.raises(SystemExit) as excinfo:
        mod.main(["--root", str(root), "--check-only"])

    assert excinfo.value.code == 1
