# CLAUDE.md — win_hermes (project)

NousResearch/hermes-agent의 **Windows 폐쇄 사내망용 포크**.
한국 의학연구자가 사내 PC에서 Ollama 로컬 LLM으로 코드 리뷰/수정에 쓰는 CLI 도구.
사용자는 **비개발자**다 — install.bat 더블클릭 한 번으로 끝나야 한다.

상위 지침: `~/CLAUDE.md` (의학연구 리포 전반의 모델 역할/스킬 매트릭스).
이 파일은 그 위에 **win_hermes 고유 규칙**을 덧씌운다.

---

## 0. 이 리포와 전역 지침의 차이

| 전역 (`~/CLAUDE.md`) | 이 리포 |
|---|---|
| SAS/R/Python 의학연구 분석 | **Python 3.12 단일** — CLI/패키징 도구 |
| NHIS 코호트, manuscript | 해당 없음 — Windows 사내망 배포물 |
| PHI 외부 API 금지 | **PHI 없음** (오픈소스 fork) — Codex/Gemini 호출 가능 |
| 결과 숫자 정확성 | **Windows에서 실제로 동작**하는 것 (CRLF, ProactorLoop, encoding) |
| 코호트 워크플로우 | install/CLI/upstream-rebase 워크플로우 |

전역 지침의 **모델 역할 매트릭스, `/advisor` 사용 시점, `superpowers` 디시플린, `gstack` 커밋 규칙, Korean/English 스타일은 그대로 적용**한다.

---

## 1. 프로젝트 좌표

- **GitHub:** https://github.com/parktg72/win_hermes.git
- **Upstream:** NousResearch/hermes-agent v0.11.0 (remote 유지, rebase 시 주의)
- **Python:** 3.12 (Windows에서는 `py -3.12`), `uv`, `pytest-asyncio`
- **타깃 환경:** Windows 10/11, PyPI/GitHub 접근 불가, Ollama 로컬 LLM
- **대상 사용자:** 비개발자 의학연구자 — 에러 메시지는 **한국어**, 종료 코드는 명시

---

## 2. 모델 역할 (전역 매트릭스를 이 리포에 매핑)

전역 매트릭스 그대로 적용. 이 리포에서 자주 닿는 부분만:

| 모델 | 이 리포에서의 용도 |
|---|---|
| **Opus 4.7** | install.bat / hermes.bat 변경, upstream rebase 결정, 8000줄 `main.py` 수정 계획, `/advisor` |
| **Sonnet 4.6** | `hermes_cli/**` 일상 구현, pytest 작성/수정, providers 추가 |
| **Haiku 4.5** | grep/find, 로그 스캔, 단순 syntax 확인 |
| **gpt-5.5 (codex review)** | Windows 호환성 가정 challenge, 폐쇄망 가정 challenge |
| **gpt-codex-5.3** | 같은 spec 병렬 구현 → diff (특히 .bat 스크립트) |
| **Gemini Pro** | upstream 변경 분량이 클 때 장문맥 비교 |

---

## 3. 사내망/Windows 고유 규칙 (Hard rules)

### 3.1 `.bat` 파일은 무조건 CRLF + UTF-8

macOS에서 .bat 작성/수정 후 **즉시** 변환:
```python
open(f,'wb').write(open(f,'rb').read().replace(b'\r\n',b'\n').replace(b'\n',b'\r\n'))
```
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

### 3.4 Wheel 벤더링

- `scripts/download_wheels.py` — `win_amd64`/`cp312` 한정으로 받는다.
- 벤더 바이너리는 **gitignore**, 릴리스 zip에만 포함.
- 새 의존성 추가 시 `pyproject.toml`만 고치지 말고 wheel 다운로드 명단/문서도 같이 갱신.
- 릴리스 빌드 절차는 **`packaging/RELEASE_CHECKLIST.md` 따른다** — 휠 개수 검증, .bat CRLF 검증, 스모크 테스트(traceback 누수 회귀 확인)까지 포함.

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

### 5.1 새 기능/버그 (이 리포 표준)

1. **Opus** — `superpowers:brainstorming`: 사용자가 비개발자라는 전제로 UX부터 정의 (어떤 메시지, 어떤 종료 코드, 어떤 한국어 안내)
2. **gpt-5.5 (`/codex challenge`)** — "Windows에서 진짜 되나?", "사내망 차단 시 어떻게 되나?" 추궁
3. **Sonnet** 구현 + **gpt-codex-5.3** 동일 spec 병렬 구현 (특히 .bat) → Opus가 diff reconcile
4. **pytest** (`tests/test_windows.py`, `tests/test_ollama_discovery.py`, `tests/test_scan.py` 등) — 통과 전엔 done 아님
5. **Opus `/advisor`** — 커밋/PR 직전 최종 사인오프
6. **gstack** 으로 commit/PR

### 5.2 Upstream rebase (NousResearch/hermes-agent 변경 따라가기)

1. 새 브랜치 생성 (절대 main에서 직접 rebase 금지)
2. `git fetch upstream && git log upstream/main ^HEAD --oneline` 으로 변경량 확인
3. **분량이 크면 Gemini Pro에 통째로 보내 conflict surface 미리 식별**
4. Windows 패치 / install 경로 / Korean 메시지가 깨지지 않았는지 grep으로 검증
5. 25개 pytest 모두 green → `/advisor` → 머지

### 5.3 커밋 규칙

전역 `gstack` 규칙 그대로 + 이 리포 추가:
- `.bat` 변경 커밋엔 "(CRLF verified)" 표기
- upstream merge 커밋엔 base SHA 명시 (`Merge upstream NousResearch@<sha>`)

---

## 6. `/advisor` 호출 지점 (이 리포 고유)

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
- `.gitattributes` 의 `*.bat eol=crlf` 제거/변경
- upstream remote URL 변경
- install.bat 사용자 대면 메시지 톤/언어 변경
- `hermes_cli/main.py`에서 서브커맨드 **삭제** (사용자 흐름이 깨질 수 있음 — 추가/수정은 OK)

전역의 "PHI 외부 API 금지"는 이 리포에는 적용되지 않는다 (이 코드베이스에 PHI 없음).

---

## 8. 스타일

- **사용자 대면 텍스트는 한국어**, 코드/주석/커밋 메시지는 사용자 선호 따름 (영문 OK)
- 에러는 "무엇이 / 왜 / 어떻게 해결" 3줄 한국어 + exit code
- 숫자/사실 → 해석 → 캐비엇 (전역 규칙 동일)
- "표준 관행" 대신 구체 근거 (Python docs, uv changelog, MS docs 링크)
