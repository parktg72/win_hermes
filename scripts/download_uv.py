#!/usr/bin/env python3
"""Download uv.exe (Windows x86_64) into vendor/uv.exe for offline install.

Run on an internet-connected machine (any OS — macOS/Linux/Windows). Two ways:

    Windows:    download_wheels.bat 더블클릭 (download_uv 자동 호출)
    Any OS:     python scripts/download_uv.py

Fetches the official astral-sh/uv release zip for win_amd64, verifies the
SHA256 checksum from the release's published `.sha256` file, extracts only
`uv.exe`, and writes it to vendor/uv.exe.

Idempotent: if vendor/uv.exe already exists and its hash matches the
expected SHA256 for the configured version, the download is skipped.

Version override:
    UV_VERSION=0.5.18 python scripts/download_uv.py
"""
from __future__ import annotations

import hashlib
import io
import os
import sys
import urllib.request
import urllib.error
import zipfile
from pathlib import Path

# Pinned default. Override via the `UV_VERSION` env var when bumping uv.
# Any version >= 0.4 should work with install.bat's `uv venv --allow-existing`
# and `uv python install` invocations.
# Pin reviewed: 2026-04-30 (uv 0.5.18 — last verified to publish .sha256
# alongside the win_amd64 zip on github.com/astral-sh/uv/releases).
DEFAULT_UV_VERSION = "0.5.18"
UV_VERSION = os.environ.get("UV_VERSION", DEFAULT_UV_VERSION).lstrip("v")

ZIP_NAME = "uv-x86_64-pc-windows-msvc.zip"
RELEASE_BASE = f"https://github.com/astral-sh/uv/releases/download/{UV_VERSION}"
ZIP_URL = f"{RELEASE_BASE}/{ZIP_NAME}"
SHA_URL = f"{ZIP_URL}.sha256"

VENDOR_DIR = Path(__file__).resolve().parent.parent / "vendor"
TARGET_EXE = VENDOR_DIR / "uv.exe"


def _http_get(url: str, *, binary: bool = False) -> bytes | str:
    req = urllib.request.Request(url, headers={"User-Agent": "win_hermes-prep/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = resp.read()
    except urllib.error.HTTPError as e:
        raise SystemExit(
            f"[오류] {url} 다운로드 실패 (HTTP {e.code}).\n"
            f"        UV_VERSION={UV_VERSION} 가 실제로 릴리스되어 있는지 확인하세요."
        )
    except urllib.error.URLError as e:
        raise SystemExit(
            f"[오류] {url} 네트워크 접근 실패: {e.reason}\n"
            f"        외부망 (PyPI/GitHub) 접속 가능한 PC에서 실행하세요."
        )
    return data if binary else data.decode("utf-8")


def _parse_sha256_line(text: str) -> str:
    """astral-sh/uv `.sha256` files are formatted as `<hex>  <filename>`.

    Be lenient: accept either a bare 64-hex-char line or the 2-column form.
    """
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        token = line.split()[0]
        if len(token) == 64 and all(c in "0123456789abcdefABCDEF" for c in token):
            return token.lower()
    raise SystemExit(f"[오류] .sha256 파싱 실패. 응답:\n{text!r}")


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().lower()


def main() -> None:
    VENDOR_DIR.mkdir(parents=True, exist_ok=True)

    print(f"=== uv.exe 다운로더 (UV_VERSION={UV_VERSION}) ===")
    print(f"릴리스 URL: {ZIP_URL}")

    print("[1/4] 공식 SHA256 체크섬 조회 중...")
    expected_sha = _parse_sha256_line(_http_get(SHA_URL))
    print(f"      expected: {expected_sha}")

    if TARGET_EXE.exists():
        print("[2/4] 기존 vendor/uv.exe 발견 — 해시 비교 중...")
        # We can't compare uv.exe hash directly to the zip's hash, so we
        # always re-download the zip on first miss and compare uv.exe bytes
        # extracted from a fresh zip. To keep idempotency without a full
        # download, persist a sidecar marker file.
        marker = TARGET_EXE.with_suffix(".exe.sha256")
        if marker.exists() and marker.read_text().strip() == expected_sha:
            print(f"      이미 최신 ({expected_sha[:12]}…). 스킵.")
            print("\n[OK] vendor/uv.exe 준비 완료.")
            return
        print("      마커 불일치 또는 없음 → 재다운로드.")

    print(f"[2/4] {ZIP_NAME} 다운로드 중...")
    blob = _http_get(ZIP_URL, binary=True)

    print("[3/4] SHA256 검증 중...")
    actual_sha = hashlib.sha256(blob).hexdigest().lower()
    if actual_sha != expected_sha:
        raise SystemExit(
            "[오류] SHA256 불일치. 다운로드가 손상되었거나 변조되었을 수 있습니다.\n"
            f"        expected: {expected_sha}\n"
            f"        actual:   {actual_sha}"
        )
    print(f"      OK ({actual_sha[:12]}…)")

    print("[4/4] zip에서 uv.exe 추출 중...")
    with zipfile.ZipFile(io.BytesIO(blob)) as zf:
        # Archive layout (cargo-dist convention):
        #   uv-x86_64-pc-windows-msvc/uv.exe
        #   uv-x86_64-pc-windows-msvc/uvx.exe
        candidates = [n for n in zf.namelist() if n.endswith("/uv.exe") or n == "uv.exe"]
        if not candidates:
            raise SystemExit(
                f"[오류] zip 안에서 uv.exe를 찾지 못했습니다. 파일 목록:\n"
                + "\n".join(zf.namelist())
            )
        member = candidates[0]
        with zf.open(member) as src, open(TARGET_EXE, "wb") as dst:
            dst.write(src.read())

    # Persist marker so re-runs are idempotent.
    TARGET_EXE.with_suffix(".exe.sha256").write_text(expected_sha + "\n")

    size_mb = TARGET_EXE.stat().st_size / (1024 * 1024)
    print(f"\n[OK] {TARGET_EXE} 작성 완료 ({size_mb:.1f} MB)")
    print("다음 단계: scripts/download_wheels.py 실행 후 vendor/ 전체를 사내망 PC로 복사")


if __name__ == "__main__":
    main()
