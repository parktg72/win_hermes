# win_hermes 사용 안내 (한국어)

Windows 사내망 PC에서 **로컬 Ollama 모델**로 코드/문서를 분석하기 위한 도구입니다.
upstream [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent)의 Windows 포크.

---

## 0. 가장 자주 묻는 질문 — 무엇을 어디서 실행하나?

> **install.bat 만으로 휠이 자동으로 받아지지 않습니다.**
> 사내망에서 PyPI(인터넷 패키지 저장소) 접근이 막혀 있다면,
> **외부망 PC에서 휠을 먼저 받은 뒤 사내망 PC로 옮겨야** 합니다.

흐름은 이렇게 둘 중 하나입니다.

### 시나리오 A — 사내망 PC에서 PyPI(인터넷)가 가능

PC가 한 대로 끝납니다.

```
[사내망 PC]
  1) install.bat 더블클릭   →  인터넷에서 직접 설치
  2) ollama serve / ollama pull <model>
  3) hermes chat .
```

### 시나리오 B — 사내망 PC에서 PyPI 접근 차단 (보통 케이스)

PC 두 대가 필요합니다.

```
[외부망 PC] (인터넷 가능)
  1) download_wheels.bat 더블클릭  →  vendor\wheels\ 폴더 자동 생성
  2) win_hermes 폴더 전체를 USB나 공유 드라이브로 복사

           │
           ▼

[사내망 PC]
  3) 복사한 폴더에서 install.bat 더블클릭   →  vendor\wheels\ 사용해 오프라인 설치
  4) ollama serve / ollama pull <model>
  5) hermes chat .
```

`install.bat`은 `vendor\wheels\` 폴더가 있으면 자동으로 그것만 사용해서 설치합니다(인터넷 안 봄). 폴더가 없으면 인터넷 설치를 시도하다 실패합니다.

---

## 1. 사전 준비

| 항목 | 확인 명령 (CMD) | 비고 |
|---|---|---|
| Python 3.12 | `py -3.12 --version` | 없으면 [python.org](https://www.python.org/downloads/release/python-3120/)에서 3.12.x 설치. **외부망 PC와 사내망 PC 양쪽 모두 필요** (시나리오 B의 경우) |
| Ollama | `ollama --version` | [ollama.com/download](https://ollama.com/download) — **사내망 PC에 설치** |
| 모델 1개 이상 | `ollama list` | 예: `ollama pull llama3.2` |

---

## 2. 시나리오 B 단계별 가이드

### 2-1. 외부망 PC에서 휠 받기

1. win_hermes 폴더를 외부망 PC에 복사 (또는 git clone).
2. 폴더 안의 **`download_wheels.bat`을 더블클릭**.
3. 진행 메시지:
   - `[1/3] Python 3.12 확인 중...`
   - `[2/3] 휠 다운로드 시작 (몇 분 걸릴 수 있습니다)...`
   - `[3/3] 완료`
4. 정상 종료되면 폴더 안에 `vendor\wheels\` 가 생기고 약 30~60개의 `.whl` 파일이 채워집니다.
5. 마지막에 `핵심 패키지 4종 확인 완료: httpx, colorama, pywinpty, prompt_toolkit` 가 보이면 성공.

문제가 생기면 창은 닫히지 않고 한국어 안내가 표시됩니다. `pause` 단계에서 메시지를 읽고 닫으세요.

### 2-2. 사내망 PC로 옮기기

`vendor\wheels\` 폴더가 포함된 **win_hermes 폴더 전체**를 USB 또는 사내 공유 드라이브로 사내망 PC에 복사.

> 핵심: `vendor\wheels\` 폴더가 빠지면 시나리오 A로 떨어져서 사내망에서 인터넷 설치 시도 → 실패합니다.

### 2-3. 사내망 PC에서 설치

복사한 폴더에서 **`install.bat`을 더블클릭**.

진행 메시지:
- `[1/4] Python 3.12 확인 중...`
- `[2/4] 가상환경 생성 중...`
- `[3/4] 의존성 설치 중...` ← 이때 `vendor\wheels\` 가 자동 사용됨
- `[4/4] 완료`

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
| `vendor\wheels 폴더 없음. 온라인 설치 시도` | 시나리오 B인데 휠이 빠짐 | 외부망 PC에서 `download_wheels.bat` 다시 실행 후 `vendor\` 폴더째 복사 |
| `Ollama가 실행되지 않았습니다.` | Ollama 데몬 미실행 | CMD에서 `ollama serve` 실행 후 재시도 |
| `Ollama에 설치된 모델이 없습니다.` | `ollama pull` 한 적 없음 | `ollama pull llama3.2` (또는 원하는 모델) |
| `Ollama 서버가 오류를 반환했습니다 (HTTP 5xx)` | Ollama 응답 이상 | Ollama 재시작 (`taskkill /im ollama.exe /f` 후 다시 실행) |
| `[오류] Python 3.12 다운로드 실패.` | Python 3.12 미설치 + 사내망 차단 | python.org에서 직접 3.12.x 설치 |
| `[경고] 핵심 패키지 누락` (외부망 PC에서) | `download_wheels.bat`이 일부 휠을 못 받음 | pip 업그레이드 (`py -3.12 -m pip install -U pip`) 후 재실행 |

---

## 5. 자주 쓰는 명령

```cmd
hermes              :: 일반 대화 시작
hermes init <폴더>  :: 분석 컨텍스트 설정
hermes chat <폴더>  :: 폴더 기반 대화
hermes model        :: 모델 변경
```

종료: 대화 중 `Ctrl+C` 또는 `exit` 입력.

---

## 6. 안전 / 보안

- **모든 LLM 호출은 로컬 Ollama** — 외부 API로 PHI(환자정보)가 나가지 않습니다.
- 분석 대상 폴더만 읽으며, 100KB 초과 파일은 자동 제외됩니다.
- 로그/대화 기록은 `~/.hermes/` 아래 사용자 홈 폴더에만 저장됩니다.
- 예상치 못한 오류 발생 시 `~/.hermes/error.log` 에 traceback이 적힙니다 (사용자 화면에는 한국어 한 줄만 표시).

---

## 7. 문의

- 설치/실행 오류: GitHub Issues — https://github.com/parktg72/win_hermes/issues
- upstream 기능 문서(영문): [`README.md`](./README.md)
