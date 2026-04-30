#!/usr/bin/env python3
"""Download Windows wheels for offline installation.

Run on an internet-connected machine (any OS). Two ways:

    Windows:    download_wheels.bat 더블클릭
    Any OS:     python scripts/download_wheels.py

Downloads win_amd64 / cp312 wheels into vendor/wheels/, then verifies
that 4 critical packages are present so missing-wheel surprises are
caught here, not on the target intranet PC.
"""
import subprocess
import sys
from pathlib import Path

VENDOR_WHEELS = Path(__file__).parent.parent / "vendor" / "wheels"

# Wheels that install.bat absolutely needs. If any are missing, abort
# loudly so the operator fixes it before zipping the release.
CRITICAL_PACKAGES = ["httpx", "colorama", "pywinpty", "prompt_toolkit"]


def _normalize(name: str) -> str:
    return name.lower().replace("-", "_")


def _verify_critical(wheels: list[Path]) -> list[str]:
    """Return list of critical package names NOT found in wheels."""
    prefixes = {_normalize(w.name.split("-")[0]) for w in wheels}
    return [pkg for pkg in CRITICAL_PACKAGES if _normalize(pkg) not in prefixes]


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
        print("pip 버전을 업그레이드(`pip install -U pip`)하거나 네트워크를 확인하세요.")
        sys.exit(1)

    wheels = list(VENDOR_WHEELS.glob("*.whl"))
    print(f"\n완료: {len(wheels)}개 wheel 파일 저장됨 → {VENDOR_WHEELS}")

    missing = _verify_critical(wheels)
    if missing:
        print(f"\n[경고] 핵심 패키지 누락: {', '.join(missing)}")
        print("이대로 사내망 PC에 옮기면 install.bat이 실패합니다.")
        print("pip을 업그레이드하거나 pyproject.toml [windows] 의존성을 확인하세요.")
        sys.exit(2)
    print(f"핵심 패키지 4종 확인 완료: {', '.join(CRITICAL_PACKAGES)}")
    print("\n다음 단계: vendor/ 폴더를 사내망 PC로 복사 후 install.bat 실행")


if __name__ == "__main__":
    main()
