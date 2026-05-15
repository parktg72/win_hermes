#!/usr/bin/env python3
"""Build the offline Windows release zip for win_hermes.

The release zip must keep ``install.bat`` and ``vendor/`` under the same
top-level prefix so the installer can find ``%~dp0vendor\\uv.exe`` after a
non-developer user extracts the archive.
"""
from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path


PREFIX = "win_hermes"
REQUIRED_FILES = (
    "pyproject.toml",
    "README.md",
    "README-KO.md",
    "LICENSE",
    "install.bat",
    "hermes.bat",
    "download_wheels.bat",
)
REQUIRED_DIRS = ("hermes_cli", "agent", "tools", "scripts")
BAT_FILES = ("install.bat", "hermes.bat", "download_wheels.bat")
EXCLUDED_DIR_NAMES = {
    ".git",
    ".pytest_cache",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
    "dist",
}
EXCLUDED_TOP_LEVEL = {
    "tests",
    "docs",
    "website",
    "tinker-atropos",
    "optional-skills",
}


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _has_crlf(path: Path) -> bool:
    data = path.read_bytes()
    return b"\r\n" in data and b"\n" not in data.replace(b"\r\n", b"")


def validate_release_tree(root: Path) -> ValidationResult:
    root = root.resolve()
    result = ValidationResult()

    for rel in REQUIRED_FILES:
        if not (root / rel).is_file():
            result.errors.append(f"missing required file: {rel}")
    for rel in REQUIRED_DIRS:
        if not (root / rel).is_dir():
            result.errors.append(f"missing required directory: {rel}")

    for rel in BAT_FILES:
        path = root / rel
        if path.exists() and not _has_crlf(path):
            result.errors.append(f"{rel} must use CRLF line endings")

    uv_exe = root / "vendor" / "uv.exe"
    if not uv_exe.is_file():
        result.errors.append("missing vendor/uv.exe")

    wheels_dir = root / "vendor" / "wheels"
    wheels = sorted(wheels_dir.glob("*.whl")) if wheels_dir.is_dir() else []
    if not wheels:
        result.errors.append("missing vendor/wheels/*.whl")
    if wheels and not any(w.name.startswith("setuptools-") for w in wheels):
        result.errors.append("vendor/wheels missing setuptools wheel")

    return result


def _include_file(path: Path, root: Path) -> bool:
    rel = path.relative_to(root)
    if any(part in EXCLUDED_DIR_NAMES for part in rel.parts):
        return False
    if rel.parts and rel.parts[0] in EXCLUDED_TOP_LEVEL:
        return False
    if path.suffix in {".pyc", ".pyo"}:
        return False
    return True


def build_release_zip(root: Path, version: str, output_dir: Path) -> Path:
    root = root.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    prefix = f"{PREFIX}-{version}"
    zip_path = output_dir / f"{prefix}.zip"

    validation = validate_release_tree(root)
    if not validation.ok:
        for error in validation.errors:
            print(f"[오류] {error}", file=sys.stderr)
        raise SystemExit(1)

    with tempfile.TemporaryDirectory(prefix="win-hermes-release-") as tmp:
        stage_root = Path(tmp) / prefix
        stage_root.mkdir()
        for src in root.rglob("*"):
            if src.is_dir() or not _include_file(src, root):
                continue
            rel = src.relative_to(root)
            dst = stage_root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for src in sorted(stage_root.rglob("*")):
                if src.is_file():
                    zf.write(src, src.relative_to(stage_root.parent).as_posix())

    return zip_path


def _print_validation(result: ValidationResult) -> None:
    if result.ok:
        print("[OK] Windows release tree validation passed.")
    for warning in result.warnings:
        print(f"[경고] {warning}")
    for error in result.errors:
        print(f"[오류] {error}", file=sys.stderr)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--version", default="v0.11.0-win.local")
    parser.add_argument("--output", type=Path, default=Path("dist"))
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args(argv)

    result = validate_release_tree(args.root)
    _print_validation(result)
    if not result.ok:
        raise SystemExit(1)
    if args.check_only:
        return

    zip_path = build_release_zip(args.root, args.version, args.output)
    print(f"[OK] release zip written: {zip_path}")


if __name__ == "__main__":
    main()
