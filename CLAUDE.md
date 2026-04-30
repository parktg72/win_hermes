# CLAUDE.md — win_hermes (project)

NousResearch/hermes-agent의 **Windows 폐쇄 사내망용 포크**.
한국 의학연구자가 사내 PC에서 Ollama 로컬 LLM으로 코드 리뷰/수정에 쓰는 CLI 도구.
사용자는 **비개발자**다 — install.bat 더블클릭 한 번으로 끝나야 한다.

상위 지침: `~/.claude/CLAUDE.md` — 모델 에이전트 매트릭스, `advisor` 호출 규칙, `superpowers` 디시플린, `gstack` 커밋 규칙, Korean/English 스타일.
이 파일은 그 위에 **win_hermes 고유 규칙만** 덧씌운다 (중복 명시는 피한다).

---

## 0. 전역과의 차이

| 전역 (`~/.claude/CLAUDE.md`) | 이 리포 |
|---|---|
| SAS/R/Python 의학연구 분석 | **Python 3.12 단일** — CLI/패키징 도구 |
| NHIS 코호트, manuscript | 해당 없음 — Windows 사내망 배포물 |
| PHI 보호 (외부 API 신중) | **PHI 없음** (오픈소스 fork) — 모든 외부 CLI 자유 호출 |
| 결과 숫자 정확성이 최상위 | **Windows에서 실제로 동작**이 최상위 (CRLF, ProactorLoop, encoding) |
| 코호트 워크플로우 | install / CLI / upstream-rebase 워크플로우 |

전역 매트릭스/규칙은 그대로 상속. 이 파일은 그 위에 win_hermes 작업에서 자주 닿는 부분만 명시.

---

## 1. 프로젝트 좌표

- **GitHub:** https://github.com/parktg72/win_hermes.git
- **Upstream:** NousResearch/hermes-agent v0.11.0 (remote 유지, rebase 시 주의)
- **Python:** 3.12 (Windows에서는 `py -3.12`), `uv`, `pytest-asyncio`
- **타깃 환경:** Windows 10/11, PyPI/GitHub 접근 불가, Ollama 로컬 LLM
- **대상 사용자:** 비개발자 의학연구자 — 에러 메시지 **한국어**, 종료 코드 명시

---

## 2. 이 리포 task별 모델 바인딩

전역 매트릭스를 이 리포에서 자주 맞닥뜨리는 작업에 매핑. 호출 문법은 전역 §Invocation 그대로.

| 작업 | 1차 (구현/계획) | 2차 (challenge / 병렬 / orient) | 마지막 게이트 |
|---|---|---|---|
| `install.bat` / `hermes.bat` 변경 | Opus 4.7 | `gpt-5.3-codex` 병렬 구현 (`.bat` 특화) | `advisor` **필수** |
| `hermes_cli/**` 일상 구현 | Sonnet 4.6 | `gpt-5.3-codex` 또는 `qwen3.6-plus` 병렬 | `advisor` (코어 변경 시) |
| `main.py` (8000줄) 수정 계획 | Opus 4.7 | `kimi-k2.6` / `gemini-3.1-pro` orientation | `advisor` |
| upstream rebase diff 스캔 | `gemini-3.1-pro` | `kimi-k2.6` 대안 | `advisor` (머지 직전) |
| Ollama / 새 provider 추가 (라우팅) | Opus 4.7 | `deepseek-v4-pro` 가정 challenge | `advisor` **필수** |
| 한국어 사용자 메시지 변경 | Opus 4.7 | `glm-5.1` 한국어 copy 검수 | `advisor` **필수** |
| pytest 작성/수정, providers 실험 | Sonnet 4.6 | `qwen3.6-plus` (수식/계산이 들어가면) | — |
| 로그 스캔 / grep / 단순 syntax | Haiku 4.5 | — | — |

상세 역할/시나리오는 `~/.claude/CLAUDE.md` §Model agents 참조.

---

## 3. 사내망 / Windows 고유 규칙 (Hard rules)

### 3.1 `.bat` 파일은 무조건 CRLF + UTF-8

macOS에서 .bat 작성/수정 후 **즉시** 변환. 두 단계로 — read-then-write를 분리하지 않으면 truncate 부작용으로 파일이 비워진다.

```python
with open(f, 'rb') as r:
    data = r.read()
with open(f, 'wb') as w:
    w.write(data.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n'))
```

⚠️ 한 줄 패턴 `open(f,'wb').write(open(f,'rb').read()...)` 는 평가 순서상 wb가 먼저 truncate되어 빈 파일이 됨 — **쓰지 말 것.**

- `.gitattributes`의 `*.bat eol=crlf`는 **체크아웃 시에만** 적용 — 새로 만든 파일은 변환 안 됨.
- Bash에서 `>nul` 문자열을 그대로 쓰면 셸이 리디렉션으로 해석한다. Python heredoc/스크립트 안에서는 `chr(62)+'nul'` 등으로 우회.

### 3.2 install.bat / hermes.bat 변경 시 반드시 보존

- `py -3.12` preflight (없으면 한국어 안내 후 exit)
- `uv venv` + `uv pip` 사용 (pip 직접 호출 금지)
- 오프라인 설치 경로: `--no-index --find-links vendor/wheels`
- mkdir 후 copy (사용자가 처음 실행할 때 디렉터리 부재 가능)
- exit code propagation (`exit /b %ERRORLEVEL%`)
- 사용자에게 보이는 메시지는 **한국어**

### 3.3 Ollama 미실행 / PyPI 차단 등은 **한국어 메시지 + exit(1)**

스택트레이스 노출 금지. `OllamaNotRunningError` 패턴을 다른 사용자-대면 에러에도 동일하게 적용.

### 3.4 Wheel / uv.exe 벤더링

- `scripts/download_uv.py` — astral-sh/uv 공식 릴리스에서 `uv.exe`를 받아 SHA256 검증 후 `vendor/uv.exe` 작성. `UV_VERSION` env로 버전 override.
- `scripts/download_wheels.py` — `win_amd64`/`cp312` 한정.
- 외부망 PC 작업은 `download_wheels.bat` 더블클릭 한 번으로 두 스크립트 모두 실행됨.
- 벤더 바이너리(`vendor/uv.exe`, `vendor/wheels/`)는 **gitignore**, 릴리스 zip에만 포함.
- 새 의존성 추가 시 `pyproject.toml`만 고치지 말고 wheel 다운로드 명단/문서도 같이 갱신.
- 릴리스 빌드 절차는 **`packaging/RELEASE_CHECKLIST.md` 따른다** — 휠 개수 + uv.exe 존재 검증, .bat CRLF 검증, 스모크 테스트(traceback 누수 회귀 확인)까지 포함.

---

## 4. 코드베이스 구조 (수정 전 알아둘 것)

### 4.1 `hermes_cli/main.py`는 8000+ 줄

- 서브커맨드 등록: `subparsers.add_parser()` + `parser.set_defaults(func=cmd_fn)` → `args.func(args)` 통합 디스패치
- 새 헬퍼 함수는 `main()` **앞에** 둔다
- `cmd_chat()` 같은 동기 함수에서 async 호출은 `asyncio.run()`
- 수정 전 `grep`으로 기존 패턴 먼저 확인 — 추측으로 추가하면 디스패치 누락 발생

### 4.2 `hermes_cli/providers/`는 패키지 (단일 파일 아님)

원래 단일 `providers.py`였던 걸 `providers/__init__.py`로 `git mv` 완료. 새 provider 추가 시 이 패키지 구조 유지 (`providers/ollama_discovery.py` 패턴 참고).

### 4.3 Windows 패치 진입점

`hermes_cli/platform/windows.py` — colorama, `ProactorEventLoop`, `PureWindowsPath` 정규화. 플랫폼별 분기는 여기로 모은다. main.py 안에 인라인 분기 추가하지 않는다.

### 4.4 스캔 한도

`hermes_cli/scan.py` — 파일당 100KB 제한, SAS/R/Python/SQL/md 확장자. 토큰 오버플로우 처리 경로 변경 시 테스트 같이 수정.

---

## 5. 워크플로우

### 5.1 새 기능/버그

전역 `~/.claude/CLAUDE.md` §"Mapping into the standard flow" 그대로 따른다. 이 리포 적용 시 짚을 점:

- 2단계 challenge:
  - `deepseek-v4-pro` → "사내망 가정 / Ollama 단독 / Windows 경로"가 진짜 깨끗한지
  - `gpt-5.3-codex-spark` → 코드 경로/race condition/edge case
- 3단계 병렬 구현:
  - `.bat` / Windows 스크립트 → **`gpt-5.3-codex`**
  - Python 코어 (`hermes_cli/**`) → **`qwen3.6-plus`** 또는 `gpt-5.3-codex`
- 5단계 peer pass:
  - 한국어 사용자 메시지가 변경됐다면 `glm-5.1`로 한국어 copy 통과 **필수**
- pytest는 win_hermes에선 다음 5종 최소 green:
  `tests/test_windows.py`, `tests/test_ollama_discovery.py`, `tests/test_main_guard.py`, `tests/test_gitattributes.py`, `tests/test_scan.py`

### 5.2 Upstream rebase

1. 새 브랜치 생성 (절대 main에서 직접 rebase 금지)
2. `git fetch upstream && git log upstream/main ^HEAD --oneline` 으로 변경량 확인
3. 분량이 크면 **`gemini-3.1-pro`** (1차) / `kimi-k2.6` (fallback) 에 통째로 보내 conflict surface 미리 식별
4. Windows 패치 / install 경로 / 한국어 메시지가 깨지지 않았는지 grep으로 검증
5. pytest 모두 green → `advisor` → 머지

### 5.3 커밋 규칙

전역 `gstack` 규칙 그대로 + 이 리포 추가:
- `.bat` 변경 커밋엔 `(CRLF verified)` 표기
- upstream merge 커밋엔 base SHA 명시 (`Merge upstream NousResearch@<sha>`)

---

## 6. `/advisor` 호출 지점 (이 리포 고유 추가)

전역 규칙 + 다음 시점 **반드시**:

- **install.bat / hermes.bat 변경** — 사용자 첫인상 망가지면 복구 불가
- **upstream rebase 머지 직전**
- **새 provider 추가** (Ollama 외 LLM 백엔드)
- **에러 메시지 한국어 변경** (사용자 대면 텍스트는 신중히)

스킵해도 되는 곳: 오타, 변수명 변경, 테스트 fixture만 손볼 때.

---

## 7. 묻고 진행 (Never without asking)

전역 규칙에 다음 추가:

- `main` 브랜치에 force-push (전역에서도 금지지만 이 리포에선 **upstream 추적이 깨질 수 있음** — 더더욱)
- `vendor/wheels/` 또는 릴리스 zip 삭제
- `.gitattributes`의 `*.bat eol=crlf` 제거/변경
- upstream remote URL 변경
- install.bat 사용자 대면 메시지 톤/언어 변경
- `hermes_cli/main.py`에서 서브커맨드 **삭제** (사용자 흐름이 깨질 수 있음 — 추가/수정은 OK)

전역의 PHI 관련 제약은 이 리포에 적용되지 않는다 (이 코드베이스에 PHI 없음).

---

## 8. 스타일

전역 그대로 + 이 리포 추가:

- **사용자 대면 텍스트는 한국어**, 코드/주석/커밋 메시지는 사용자 선호 (영문 OK)
- 에러는 **"무엇이 / 왜 / 어떻게 해결" 3줄 한국어 + exit code**
- "표준 관행" 대신 구체 근거 (Python docs, uv changelog, MS docs 링크)
