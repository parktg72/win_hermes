from pathlib import Path
import subprocess


REPO_ROOT = Path(__file__).resolve().parents[2]
SETUP_SCRIPT = REPO_ROOT / "setup-hermes.sh"
INSTALL_PS1 = REPO_ROOT / "scripts" / "install.ps1"
VENDOR_UV = REPO_ROOT / "vendor" / "uv.exe"
VENDOR_README = REPO_ROOT / "vendor" / "README.md"


def test_setup_hermes_script_is_valid_shell():
    result = subprocess.run(["bash", "-n", str(SETUP_SCRIPT)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_setup_hermes_script_has_termux_path():
    content = SETUP_SCRIPT.read_text(encoding="utf-8")

    assert "is_termux()" in content
    assert ".[termux]" in content
    assert "constraints-termux.txt" in content
    assert "$PREFIX/bin" in content
    assert "Skipping tinker-atropos on Termux" in content


def test_install_ps1_checks_windows_uv_locations():
    content = INSTALL_PS1.read_text(encoding="utf-8")

    assert "$env:LOCALAPPDATA\\uv\\bin\\uv.exe" in content
    assert "$env:APPDATA\\uv\\bin\\uv.exe" in content
    assert "vendor\\uv.exe" in content
    assert "Split-Path -Parent $PSScriptRoot" in content


def test_vendor_uv_exe_is_bundled_for_offline_windows_installs():
    assert VENDOR_UV.is_file(), "vendor/uv.exe must be committed for offline Windows setup"
    assert VENDOR_UV.read_bytes()[:2] == b"MZ"


def test_vendor_uv_readme_documents_source():
    content = VENDOR_README.read_text(encoding="utf-8")

    assert "astral-sh/uv" in content
    assert "uv-x86_64-pc-windows-msvc.zip" in content
