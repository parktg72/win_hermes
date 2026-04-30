# win_hermes 릴리스 체크리스트 (한국어)

사내망 Windows PC에 배포할 zip을 만드는 절차. 외부망 가능한 macOS/Linux/Windows 어디서나 빌드 가능.
**Python 3.12 + uv 설치 PC에서 수행한다.**

---

## 1. 사전 점검

- [ ] `git status` 깨끗 (커밋되지 않은 변경 없음)
- [ ] 현재 브랜치가 의도한 릴리스 베이스인지 확인 (`git log --oneline -5`)
- [ ] `git tag` 으로 기존 태그 확인 — 다음 버전 정함 (예: `v0.11.0-win.1`)

---

## 2. 휠 다운로드 (오프라인 설치용)

외부망(PyPI 가능) PC에서. 둘 중 하나:

```bash
# Windows에서 더블클릭 (권장):
download_wheels.bat

# 또는 명령줄 (macOS/Linux/Windows):
python scripts/download_wheels.py
```

스크립트가 끝나면 핵심 패키지 4종(httpx, colorama, pywinpty, prompt_toolkit)을
자동 검증하고 누락 시 종료 코드 2로 실패합니다.

검증 (스크립트가 실패하지 않으면 자동 통과 — 아래는 수동 더블체크용):

- [ ] `vendor/wheels/` 디렉터리 존재
- [ ] `ls vendor/wheels/*.whl | wc -l` ≥ 30 (대략 — pyproject `[windows]` extra 의존성 트리)
- [ ] 스크립트 마지막 출력에 `핵심 패키지 4종 확인 완료` 보임

문제 발생 시:
- pip 22 이상에서 `--only-binary :all:` 실패 → `pip install -U pip` 후 재시도
- 특정 패키지가 wheel 없음 → 해당 의존성을 `pyproject.toml [project.optional-dependencies] windows`에서 점검 (sdist만 있는 패키지는 폐쇄망 빌드 어려움 → 대체 라이브러리 검토)

---

## 3. .bat 파일 검증

```bash
file install.bat hermes.bat
```

- [ ] 두 파일 모두 출력에 `CRLF line terminators` 포함
- [ ] `head -2 install.bat` 첫 줄에 `chcp 65001 >nul` 보임
- [ ] `grep "exit /b" hermes.bat` 1회 이상 매치 (exit code 전파)

CRLF가 아닐 경우 (macOS에서 새로 만든 직후 등):
```bash
python -c "f='install.bat'; open(f,'wb').write(open(f,'rb').read().replace(b'\r\n',b'\n').replace(b'\n',b'\r\n'))"
```
hermes.bat에도 동일 적용.

---

## 4. 테스트

```bash
uv run pytest tests/ -q
```

- [ ] 전부 통과. 실패 1개라도 있으면 릴리스 중단.
- [ ] 특히 `tests/test_windows.py`, `tests/test_ollama_discovery.py`, `tests/test_main_guard.py`, `tests/test_gitattributes.py`, `tests/test_scan.py` 모두 green.

---

## 5. 릴리스 zip 빌드

포함할 것 / 제외할 것:

| 포함 | 제외 |
|---|---|
| `hermes_cli/`, `hermes_*.py`, `pyproject.toml`, `uv.lock` | `.git/`, `__pycache__/`, `*.pyc` |
| `install.bat`, `hermes.bat` | `tests/`, `docs/`, `website/` |
| `vendor/wheels/` (오프라인 설치 핵심) | `tinker-atropos/`, `optional-skills/`, `temp_vision_images/` |
| `README.md`, `README-KO.md`, `CLAUDE.md`, `LICENSE` | `node_modules/`, `package-lock.json` |
| `scripts/download_wheels.py` (재배포 시 참고용) | 기타 사내 비공개 자료 |

빌드 명령 예시 (macOS):

```bash
VERSION=v0.11.0-win.1
git archive --format=zip --prefix=win_hermes-${VERSION}/ HEAD -o /tmp/win_hermes-${VERSION}.zip
# vendor/wheels는 git에 없으므로 별도 추가:
zip -r /tmp/win_hermes-${VERSION}.zip vendor/wheels -x "*.pyc"
```

확인:

- [ ] `unzip -l /tmp/win_hermes-${VERSION}.zip | grep -c "\.whl$"` 가 휠 개수와 일치
- [ ] `unzip -l /tmp/win_hermes-${VERSION}.zip | grep -E "(install|hermes)\.bat$"` 두 줄 출력
- [ ] zip 크기가 비정상적으로 크지 않음 (대략 ~150~300MB 예상)

---

## 6. 스모크 테스트 (가능하면 깨끗한 Windows VM)

1. zip 압축 해제
2. `install.bat` 더블클릭
3. CMD 열고 `hermes --version` 출력 확인
4. Ollama 미실행 상태에서 `hermes chat .` 실행 → **한국어 에러 + exit(1)** 확인 (traceback이 보이면 회귀 — 릴리스 중단)
5. `ollama serve` 실행 후 다시 `hermes chat .` → 모델 선택 화면 동작

체크리스트:
- [ ] traceback 노출 없음
- [ ] 모든 에러 메시지 한국어
- [ ] Ctrl+C 누르면 깨끗하게 종료 (exit 130)

---

## 7. 사용자 전달

- [ ] zip 파일 + 아래 안내문 1줄 같이 전달
  > 압축 풀고 `install.bat`을 더블클릭하세요. 자세한 안내는 폴더 안 `README-KO.md`.
- [ ] git tag + push
  ```bash
  git tag ${VERSION}
  git push origin ${VERSION}
  ```

---

## 8. 사후 (옵션)

- [ ] `~/.hermes/error.log`이 사용자 PC에 쌓이는지 1주 후 점검 (반복 오류 패턴 발견)
- [ ] upstream NousResearch/hermes-agent에 새 릴리스 떴는지 확인 → 다음 fork 릴리스 계획

---

## 자주 묻는 문제

- **Q: `download_wheels.py`가 일부 실패해도 진행해도 되나?**
  A: 안 됩니다. install.bat이 사내망에서 해당 패키지를 못 받아 실패합니다. 실패한 패키지를 확인하고 수동으로 받거나(`pip download <pkg> --platform win_amd64 --python-version 3.12 --only-binary :all: -d vendor/wheels`), 의존성에서 제거하세요.

- **Q: 사용자 PC에 Python 3.12가 없습니다.**
  A: install.bat이 `py -3.12`로 preflight합니다. 없으면 한국어 안내 후 종료. python.org에서 3.12.x 직접 설치하도록 사용자에게 가이드.

- **Q: vendor/wheels을 zip에 넣지 않으면?**
  A: install.bat은 `--no-index --find-links vendor/wheels`로 시도하다 폴더가 없으면 온라인 fallback 시도. 사내망에선 즉시 실패. **반드시 포함.**
