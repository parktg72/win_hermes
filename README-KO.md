# win_hermes 사용 안내 (한국어)

Windows 사내망 PC에서 **로컬 Ollama 모델**로 코드/문서를 분석하기 위한 도구입니다.
upstream [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent)의 Windows 포크.

---

## 1. 사전 준비

다음이 PC에 설치되어 있어야 합니다.

| 항목 | 확인 명령 (CMD) | 비고 |
|---|---|---|
| Python 3.12 | `py -3.12 --version` | 없으면 [python.org](https://www.python.org/downloads/release/python-3120/)에서 3.12.x 설치 |
| Ollama | `ollama --version` | [ollama.com/download](https://ollama.com/download) |
| 모델 1개 이상 | `ollama list` | 예: `ollama pull llama3.2` |

사내망에서 PyPI 접근이 막혀 있다면, **PyPI 접근 가능한 PC**에서 먼저
`python scripts/download_wheels.py`를 실행해 `vendor/wheels/` 폴더를 만들어 함께 옮기세요.

---

## 2. 설치

`install.bat` 파일을 **더블클릭**하면 끝납니다.

진행 중 보이는 메시지:
- `[1/4] Python 3.12 확인 중...`
- `[2/4] 가상환경 생성 중...`
- `[3/4] 의존성 설치 중...` (오프라인 휠이 있으면 자동 사용)
- `[4/4] 완료`

문제가 생기면 창은 닫히지 않고 한국어 안내가 표시됩니다.

---

## 3. 첫 실행

CMD 또는 탐색기 주소창에서 분석할 폴더로 이동 후:

```cmd
hermes init .
hermes chat .
```

- `hermes init .` — 현재 폴더 컨텍스트 설정 (한 번만)
- `hermes chat .` — 대화 시작

처음 `chat` 실행 시 **Ollama 모델 선택 화면**이 나옵니다 — 번호를 입력하세요.
선택은 `~/.hermes/config.json`에 저장되어 다음 실행부터는 자동 적용됩니다.

---

## 4. 자주 발생하는 문제

| 메시지 | 원인 | 해결 |
|---|---|---|
| `Ollama가 실행되지 않았습니다.` | Ollama 데몬 미실행 | CMD에서 `ollama serve` 실행 후 재시도 |
| `Ollama 서버가 오류를 반환했습니다 (HTTP 5xx)` | Ollama 응답 이상 | Ollama 재시작 (`taskkill /im ollama.exe /f` 후 다시 실행) |
| `[오류] Python 3.12 다운로드 실패.` | Python 3.12 미설치 + 사내망 차단 | python.org에서 직접 3.12.x 설치 |
| `vendor\wheels 폴더 없음. 온라인 설치 시도` | 오프라인 휠 미준비 + PyPI 차단 | 외부 PC에서 `download_wheels.py` 실행 후 폴더 복사 |

---

## 5. 자주 쓰는 명령

```cmd
hermes              :: 일반 대화 시작
hermes init <폴더>  :: 분석 컨텍스트 설정
hermes chat <폴더>  :: 폴더 기반 대화
hermes model        :: 모델 변경
```

---

## 6. 안전 / 보안

- **모든 LLM 호출은 로컬 Ollama** — 외부 API로 PHI(환자정보)가 나가지 않습니다.
- 분석 대상 폴더만 읽으며, 100KB 초과 파일은 자동 제외됩니다.
- 로그/대화 기록은 `~/.hermes/` 아래 사용자 홈 폴더에만 저장됩니다.

---

## 7. 문의

- 설치/실행 오류: GitHub Issues — https://github.com/parktg72/win_hermes/issues
- upstream 기능 문서(영문): [`README.md`](./README.md)
