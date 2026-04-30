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
