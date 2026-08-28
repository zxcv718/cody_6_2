# ai-gitgen — AI 기반 Git 커밋/PR 초안 생성기

`git status`·`git diff`를 읽어 **커밋 메시지**와 **Pull Request 초안**을 자동으로 생성하는 CLI 도구입니다.
Codyssey 공개 API(Anthropic 규격)를 사용하며, 생성 결과는 터미널에 출력되어 그대로 복사해 쓸 수 있습니다.

```
git diff  ─→  마스킹/절단  ─→  프롬프트 조립  ─→  AI API  ─→  형식 검증  ─→  터미널 출력
```

---

## 1. 요구 사항

| 항목 | 값 |
|---|---|
| Python | 3.10 이상 |
| 의존성 | `requests` |
| 실행 위치 | **Git이 초기화된 프로젝트 루트** |
| API 키 | Codyssey 공개 API 키 (Anthropic 호환) |

---

## 2. 설치

```bash
git clone https://github.com/zxcv718/cody_6_2.git
cd cody_6_2

python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

> `source .venv/bin/activate`를 빼먹으면 `ModuleNotFoundError: No module named 'requests'`가 납니다.
> 시스템 `python3`가 아니라 가상환경의 `python`으로 실행해야 합니다.

---

## 3. API 키 설정

키는 **환경변수로만** 읽습니다. 코드에 하드코딩하지 않으며, 프로그램은 설정 파일을 파싱하지 않습니다.

```bash
export AI_API_KEY="sk-cody-live-YOUR_KEY"
```

매번 입력하기 번거로우면 `.env`를 쓰세요. 이 파일은 `.gitignore`에 걸려 있어 커밋되지 않습니다.

```bash
cp .env.example .env       # 열어서 키를 채운다
source .env
```

**실행 시 한 줄로:**

```bash
source .venv/bin/activate && source .env
```

키가 없으면 다음과 같이 안내하고 종료합니다(exit code 1).

```
[ERROR] AI_API_KEY 환경변수가 설정되지 않았습니다.
       예) export AI_API_KEY="sk-cody-live-YOUR_KEY"
       키 발급: https://usr.codyssey.kr/public-api-console
```

---

## 4. 사용법

```bash
python main.py commit        # 커밋 메시지 초안 생성
python main.py pr            # PR 제목/본문 초안 생성
```

### 4-1. 옵션

모든 옵션은 `commit`·`pr` 양쪽에서 동일하게 쓸 수 있습니다.
과제 예시 표기(`-model`)를 위해 **하이픈 1개·2개 모두** 받습니다.

| 옵션 | 기본값 | 설명 |
|---|---|---|
| `-model`, `--model` | `claude-haiku-4` | 사용할 모델 |
| `-temperature`, `--temperature` | `0.2` | 무작위성 **0.0 ~ 1.0** |
| `-max-tokens`, `--max-tokens` | commit `700` / pr `1200` | 출력 토큰 상한 |
| `--scope` | `all` | `all` / `staged` / `unstaged` |
| `-safe-mode`, `--safe-mode` | (기본 ON) | 민감정보 마스킹 켜기 |
| `--no-safe-mode` | — | 민감정보 마스킹 끄기 (전송량 제한은 유지) |
| `--max-files` | `10` | 전송할 최대 파일 수 |
| `--max-lines` | `200` | 전송할 최대 diff 줄 수 |
| `--no-retry` | (재생성 허용) | API 호출을 1회로 고정 |
| `--dry-run` | — | **API를 호출하지 않고** 프롬프트만 출력 |

### 4-2. 사용 예시

```bash
# 기본 실행
python main.py commit

# 품질 우선 (차감 배수 1배)
python main.py pr --model claude-sonnet-4 --max-tokens 1500

# 결정적 출력 — 같은 diff에서 같은 결과를 재현하고 싶을 때
python main.py commit --temperature 0.0

# 토큰을 쓰지 않고 전송될 프롬프트만 확인
python main.py commit --dry-run

# 스테이징한 것만 요약 (실제 커밋될 내용과 정확히 일치)
python main.py commit --scope staged

# 큰 저장소에서 전송량 줄이기
python main.py pr --max-files 5 --max-lines 120
```

---

## 5. 출력 예시

아래는 **이 저장소 자신을 대상으로 실제 실행한 결과**입니다.
전체 검증 기록은 [`docs/verification.md`](docs/verification.md)에 있습니다.

### 5-1. 커밋 메시지 생성

```
$ python main.py commit

[INFO] 현재 브랜치: main
[INFO] Git status 수집 완료: 12개 파일 변경 감지
         - 미추적: .env.example
         - 미추적: .gitignore
         - 미추적: README.md
         - 미추적: ai_client.py
         - 미추적: docs/design-notes.md
         - 미추적: docs/verification.md
         - 미추적: formatter.py
         - 미추적: gitctx.py
         - 미추적: main.py
         - 미추적: prompts.py
         - 미추적: requirements.txt
         - 미추적: sanitizer.py
[INFO] Git diff 수집 완료: 2343줄 (+2260 / -0)
[INFO] 민감정보 3건 마스킹 ([MASKED_API_KEY]×2, [MASKED_SECRET]×1)
[INFO] 파일 2개 생략 (상한 초과)
[INFO] diff 2132줄 생략 (상한 초과)
[INFO] AI API 요청 중... (model=claude-haiku-4, temperature=0.2, max_tokens=700)
[DONE] 커밋 메시지 생성 완료

--- Commit Message -----------------------------------------
feat: AI 기반 Git 커밋/PR 초안 생성 CLI 도구 초기 구현

- main.py, ai_client.py, prompts.py: AI API 연동 및 프롬프트 조립 로직 구현
- gitctx.py: git status/diff 수집 및 파일 범위 제어 기능 추가
- formatter.py, sanitizer.py: 출력 형식 검증 및 민감정보 마스킹 처리
- README.md, docs/: 설치·사용법·검증 기록 문서화
- .env.example, .gitignore, requirements.txt: 프로젝트 설정 및 의존성 관리
------------------------------------------------------------
[INFO] AI API 호출 횟수: 1회 | 사용량: 입력 3826 + 출력 200 토큰 (차감배수 0.5배)
[INFO] 생성된 문구는 초안입니다. 반드시 검토 후 사용하세요.
```

### 5-2. PR 초안 생성

```
$ python main.py pr

[INFO] AI API 요청 중... (model=claude-haiku-4, temperature=0.2, max_tokens=1200)
[DONE] PR 초안 생성 완료

--- PR Title -----------------------------------------------
chore: 초기 커밋 - AI 기반 Git 커밋/PR 초안 생성기
------------------------------------------------------------

--- PR Body ------------------------------------------------
## Why
- 저장소의 첫 커밋으로, Git 변경사항을 읽어 AI를 통해 커밋 메시지와 PR 초안을 자동 생성하는 도구를 제공합니다.
- Codyssey 공개 API를 활용하여 개발자의 반복적인 메시지 작성 작업을 자동화합니다.

## What
- `main.py`: commit/pr 명령을 지원하는 CLI 진입점
- `ai_client.py`: Codyssey API 호출 및 응답 처리 모듈
- `gitctx.py`: Git status/diff 수집 및 마스킹 처리
- `formatter.py`: AI 응답 형식 검증 및 정렬
- `sanitizer.py`: 민감정보(API 키, 시크릿) 마스킹
- `prompts.py`: 커밋/PR 생성용 프롬프트 템플릿
- `README.md`: 설치, 설정, 사용법 및 예시 문서
- `docs/design-notes.md`: 아키텍처 및 설계 결정사항
- `docs/verification.md`: 실행 검증 기록
- `.env.example`: 환경변수 설정 템플릿
- `.gitignore`: API 키 등 민감정보 커밋 방지
- `requirements.txt`: Python 의존성 명시

## How to Test
- 가상환경 설정: `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
- API 키 설정: `export AI_API_KEY="[발급받은_키]"`
- 커밋 메시지 생성 테스트: `python main.py commit --dry-run`
- PR 초안 생성 테스트: `python main.py pr --dry-run`
- 실제 API 호출 테스트: `python main.py commit`
- 옵션 검증: `python main.py commit --temperature 0.0 --max-tokens 500`
------------------------------------------------------------
[INFO] AI API 호출 횟수: 1회 | 사용량: 입력 3816 + 출력 708 토큰 (차감배수 0.5배)
[INFO] 생성된 문구는 초안입니다. 반드시 검토 후 사용하세요.
```

> ⚠️ 위 출력에 **실제로 사실이 틀린 부분이 있습니다.** `gitctx.py`를 "Git status/diff 수집 및
> **마스킹 처리**"라고 썼지만 마스킹은 `sanitizer.py`의 역할입니다. 형식은 완벽한데 내용이
> 틀린 이런 오류는 형식 검증으로 잡을 수 없습니다 — **AI 출력을 반드시 검토해야 하는 이유**입니다.

### 5-3. 변경 사항이 없을 때

```
$ python main.py commit

[INFO] 현재 브랜치: main
[INFO] Git status 수집 완료: 0개 파일 변경 감지
[INFO] 변경 사항이 없습니다. 생성하지 않고 종료합니다.
```

exit code는 **0**입니다. 사용자가 잘못한 것이 없으므로 오류가 아니며, API도 호출하지 않습니다.

### 5-4. 형식 규칙 위반 → 재생성 → 후처리 착지

`--max-tokens`가 부족해 응답이 잘린 경우입니다.

```
$ python main.py pr --max-tokens 200

[WARN] 응답이 max_tokens(200)에 걸려 잘렸습니다. --max-tokens를 늘리면 개선됩니다.
[WARN] 형식 규칙 위반으로 재생성합니다 (2회차): PR 본문에 `## How to Test` 섹션이 없습니다.
[WARN] 응답이 max_tokens(200)에 걸려 잘렸습니다. --max-tokens를 늘리면 개선됩니다.
[DONE] PR 초안 생성 완료
...
## How to Test
- (AI가 생성하지 못했습니다 — 직접 작성이 필요합니다)
------------------------------------------------------------
[WARN] `## How to Test` 섹션이 스텁으로 채워졌습니다 — 직접 작성이 필요합니다.
[INFO] AI API 호출 횟수: 2회 | 사용량: 입력 7017 + 출력 400 토큰 (차감배수 0.5배)
```

잘린 응답도 **HTTP 200으로 돌아옵니다.** `stop_reason`을 확인해야만 알 수 있으며,
섹션 누락은 후처리로 만들 수 없는 *정보 부족*이므로 재생성으로 대응합니다.
재생성에도 실패하면 스텁으로 착지하고 무엇이 비었는지 알립니다.

### 5-5. temperature에 따른 차이

같은 diff에 `--temperature` 값만 바꿔 3회 실행했습니다.

| 실행 | temperature | 출력 토큰 | 불릿 수 | 결과 |
|---|---|---|---|---|
| A | 0.0 | 200 | 5 | 기준 |
| B | 0.0 | 200 | 5 | **A와 완전히 동일 — 재현 가능** |
| C | 1.0 | 283 | 8 | 제목·불릿·표현 모두 달라짐 |

**A / B (temperature 0.0) — 두 번 모두 동일**

```
feat: AI 기반 Git 커밋/PR 초안 생성 CLI 도구 초기 구현

- main.py, ai_client.py, prompts.py: AI API 연동 및 프롬프트 조립 로직 구현
- gitctx.py: git status/diff 수집 및 파일 범위 제어 기능 추가
- formatter.py, sanitizer.py: 출력 형식 검증 및 민감정보 마스킹 처리
- README.md, docs/: 설치·사용법·검증 기록 문서화
- .env.example, .gitignore, requirements.txt: 프로젝트 설정 및 의존성 관리
```

**C (temperature 1.0)**

```
feat: AI 기반 Git 커밋/PR 초안 생성기 초기 구현

- ai_client.py: Codyssey API 호출 및 응답 처리 모듈 추가
- main.py: commit/pr 커맨드 CLI 진입점 및 옵션 파싱 구현
- prompts.py: 커밋 메시지와 PR 초안용 프롬프트 템플릿 정의
- gitctx.py: git status/diff 수집 및 git 상태 추출 로직 구현
- formatter.py: API 응답의 형식 검증 및 터미널 출력 처리
- sanitizer.py: 민감정보(API 키, 시크릿) 마스킹 및 전송량 제한
- .env.example, .gitignore: 환경변수 및 보안 설정 추가
- README.md, docs/: 설치·사용법·검증 기록 문서 작성
```

`temperature=0.0`은 **재현 가능**합니다. 프롬프트를 개선할 때 변경 효과만 분리해서
관찰할 수 있는 이유이며, 그래서 이 값을 CLI 옵션으로 뺐습니다.

> ⚠️ **차이를 보려면 조건이 필요합니다.**
> 위 수치는 2,343줄짜리 diff에서 측정한 것입니다. **변경이 작으면 temperature를 올려도
> 결과가 거의 같습니다** — 요약할 방법이 몇 가지 없기 때문입니다.
> 실제로 18줄짜리 diff에서는 `0.0`과 `1.0`이 56 대 59토큰으로 거의 차이가 없었습니다.
>
> 마찬가지로 `--max-tokens`도 **자연 출력 길이보다 낮게** 잡아야 절단이 일어납니다.
> 도구가 매 실행 끝에 `출력 N 토큰`을 알려주므로, 한 번 돌려보고 그보다 낮은 값을 주세요.
>
> | 보고 싶은 것 | 조건 |
> |---|---|
> | temperature 차이 | 파일 여러 개를 실제로 고친 diff (수백 줄 이상) |
> | max_tokens 절단·재생성 | `출력 N 토큰`보다 작은 값 (예: `--max-tokens 30`) |

---

## 6. 동작 원리

```
main.py            CLI 조립 — 로직 없음, 계층을 연결만 한다
  │
  ├─ gitctx.py     [수집]  git status/diff → GitContext        (로컬·결정적·무료)
  ├─ sanitizer.py  [보안]  마스킹 + 절단 — 외부로 나가는 단일 관문
  ├─ prompts.py    [부탁]  시스템/사용자 프롬프트 조립          (확률적, 보장 없음)
  ├─ ai_client.py  [호출]  /v1/messages + 예외 매핑            (원격·유료)
  └─ formatter.py  [강제]  길이/형식 검증 + 후처리              (결정적, 보장 있음)
```

계층을 나눈 이유는 [`docs/design-notes.md`](docs/design-notes.md)에 정리했습니다.

### 문서 안내

| 문서 | 내용 |
|---|---|
| [`docs/qna.md`](docs/qna.md) | 평가항목표 18개 항목별 답변 (한 줄 답 → 근거 → 확인 방법) |
| [`docs/design-notes.md`](docs/design-notes.md) | 설계 배경 상세 — 왜 이 구조를 골랐는가 |
| [`docs/verification.md`](docs/verification.md) | 기능별 실행 증빙, 마스킹 오탐 테스트 14케이스 |

---

## 7. 민감정보 대응 (safe-mode)

`git diff`에는 `.env` 수정 내역, 하드코딩된 키, 테스트 픽스처의 개인정보가 섞일 수 있습니다.
이 도구는 **프롬프트 조립 직전 단일 관문**(`sanitizer.sanitize()`)을 통과시켜 두 가지를 동시에 적용합니다.

### (A) 마스킹 — 기본 ON

`sanitizer.py`의 `MASK_RULES`에 정의된 패턴을 자리표시자로 치환한 뒤 전송합니다.

| 대상 | 패턴 | 치환 |
|---|---|---|
| 개인키 블록 | `-----BEGIN … PRIVATE KEY-----` ~ `-----END …-----` | `[MASKED_PRIVATE_KEY]` |
| OpenAI/Anthropic/Codyssey 키 | `sk-` + 12자 이상 | `[MASKED_API_KEY]` |
| GitHub 토큰 | `ghp_` `gho_` `ghu_` `ghs_` `ghr_` + 16자 이상 | `[MASKED_GITHUB_TOKEN]` |
| AWS Access Key | `AKIA` / `ASIA` + 16자 | `[MASKED_AWS_KEY]` |
| Google API 키 | `AIza` + 35자 | `[MASKED_GOOGLE_KEY]` |
| Slack 토큰 | `xoxb-` `xoxp-` `xoxa-` `xoxr-` `xoxs-` | `[MASKED_SLACK_TOKEN]` |
| JWT | `eyJ…` 형태 base64url 3토막 | `[MASKED_JWT]` |
| 키=값 (문자열 리터럴) | `PASSWORD = "…"` 등, 값 8자 이상 | `[MASKED_SECRET]` |
| `.env` 스타일 | `SECRET_TOKEN=…` (`=` 앞뒤 공백 없음) | `[MASKED_SECRET]` |
| 주민등록번호 | `000000-0000000` | `[MASKED_RRN]` |
| 신용카드 번호 | `0000-0000-0000-0000` | `[MASKED_CARD]` |
| 휴대폰 번호 | `010-0000-0000` 등 | `[MASKED_PHONE]` |
| 이메일 | `user@domain.tld` | `[MASKED_EMAIL]` |

**설계 기준** (명세에 구체적 목록이 없어 자체 판단했습니다)

1. **구조가 뚜렷해 오탐이 낮은 것부터** 잡습니다. 발급 기관이 정한 접두사(`sk-`, `AKIA`)는 우연히 일치할 일이 거의 없습니다. 반대로 "비밀번호처럼 생긴 문자열"을 잡으려 하면 코드 전체가 마스킹됩니다.
2. **치환문자열에 종류를 남깁니다.** `[MASKED]`가 아니라 `[MASKED_EMAIL]`로 쓰면 AI가 "이메일 관련 변경"임을 알 수 있어 요약 품질이 유지됩니다. **가리는 것은 값이지 맥락이 아닙니다.**
3. **키=값에서는 값만** 가리고 키 이름은 남깁니다. `API_KEY = "[MASKED_SECRET]"`은 설정 변경임을 알 수 있지만, 줄 전체를 가리면 무슨 변경인지 알 수 없습니다.
4. **구체적 규칙을 일반 규칙보다 앞에** 둡니다. `API_KEY = "sk-…"`는 먼저 `[MASKED_API_KEY]`가 되고, 뒤따르는 일반 규칙은 이미 마스킹된 값을 건너뜁니다.

**오탐 방지 장치**

| 구분선 | 이유 |
|---|---|
| 값에 **따옴표 필수** | `PASSWORD = "hunter2"`는 비밀, `password = user.password`는 코드. 따옴표가 이 둘을 가릅니다 |
| 값 **8자 이상** | `TOKEN_TYPE = "Bearer"`(6자), `MODE = "test"`(4자) 같은 비밀 아닌 값을 걸러냅니다 |
| `.env` 규칙은 **`=` 앞뒤 공백 금지** | `.env`는 `KEY=value`, 파이썬은 `key = value`. 이 한 글자 차이가 설정 파일과 코드를 가릅니다 |
| 카드번호는 4-4-4-4 | UUID(8-4-4-4-12)와 자릿수가 달라 충돌하지 않습니다 |

**한계** — 정규식은 **형식이 있는 것만** 잡습니다. 내부 서버 주소, 사람 이름, 사업 로직 같은 비정형 비밀은 잡을 수 없습니다. 마스킹은 최후 방어선이 아니라 **안전망**이며, 근본 대책은 애초에 비밀을 커밋하지 않는 것입니다.

### (B) 전송량 제한 — 항상 적용

| 항목 | 기본 상한 | 옵션 |
|---|---|---|
| 파일 수 | **10개** | `--max-files` |
| diff 줄 수 | **200줄** | `--max-lines` |

파일 경계(`diff --git`)로 먼저 쪼갠 뒤 자르므로, 절단되어도 각 조각이 유효한 diff로 남습니다.

**`--no-safe-mode`는 (A)만 끕니다.** (B)는 보안 기능이자 비용 방어 기능이라 항상 유지됩니다.

```
$ python main.py commit --dry-run                    # safe-mode ON
+API_KEY = "[MASKED_API_KEY]"

$ python main.py commit --dry-run --no-safe-mode     # safe-mode OFF
[WARN] safe-mode가 꺼져 있습니다 — diff의 민감정보가 그대로 전송됩니다.
+API_KEY = "sk-cody-live-SECRET1234567890abc"
```

마스킹·절단이 일어나면 `[INFO]`로 무엇을 가렸는지 알리고, **AI에게도 알립니다.**
모르면 `[MASKED_API_KEY]`라는 자리표시자 자체를 변경 내용으로 착각해 요약하기 때문입니다.

### 그 외 주의사항

- **생성된 문구는 최종본이 아닙니다.** 반드시 검토 후 적용하세요.
- 모든 호출은 Codyssey에 감사 로그로 기록되며, 프롬프트·응답이 콘텐츠 이력으로 저장됩니다.
- 키가 유출됐다고 판단되면 즉시 콘솔에서 폐기하고 재발급하세요.
- `.gitignore`는 **이미 추적 중인 파일에는 효력이 없습니다.** 실수로 키를 커밋했다면
  `git rm --cached`로 추적을 끊고 **키를 폐기**해야 합니다.

---

## 8. 비용 / 요청 횟수 제한

### 8-1. 호출 횟수

**1회 실행 = API 호출 1회**가 원칙입니다. 형식 검증에 실패했을 때만 **최대 1회 재생성**합니다(총 2회 상한).

- 상한은 `ai_client.MAX_CALLS_PER_RUN = 2`로 코드에 강제되어 있습니다. 무한 재시도 루프는 존재하지 않습니다.
- `--no-retry`로 1회 고정할 수 있습니다.
- 실행이 끝나면 항상 실제 호출 횟수와 토큰 사용량을 출력합니다.

### 8-2. 모델별 차감 배수

월 한도(5,000,000 토큰)에서 깎이는 배수가 모델마다 다릅니다.

| 모델 ID | 실제 모델 | 차감 배수 | 권장 용도 |
|---|---|---|---|
| `claude-haiku-4` | Claude Haiku 4.5 | **0.5×** | 기본값 — 개발·반복 테스트 |
| `claude-sonnet-4` | Claude Sonnet 4.6 | 1× | 최종 결과물 |
| `claude-opus-4-7` | Claude Opus 4.7 | 1.5× | — |
| `claude-opus-4-8` | Claude Opus 4.8 | 1.5× | — |

### 8-3. 권장 사용법

- 프롬프트를 다듬는 동안에는 **`--dry-run`**을 쓰세요. API를 전혀 호출하지 않습니다.
- 반복 실험은 `claude-haiku-4`(0.5배)로, 최종 결과물만 `claude-sonnet-4`로 뽑으세요.
- 큰 저장소에서는 `--max-lines`를 줄이면 입력 토큰이 그만큼 줄어듭니다.
- 사용량은 콘솔 **[사용량]** 탭에서 확인할 수 있습니다.

---

## 9. 문제 해결

| 증상 | 원인 | 해결 |
|---|---|---|
| `ModuleNotFoundError: requests` | 가상환경 미활성화 | `source .venv/bin/activate` |
| `[ERROR] AI_API_KEY 환경변수가...` | 키 미설정 | `export AI_API_KEY="..."` 또는 `source .env` |
| `[ERROR] Git 저장소가 아닙니다` | 저장소 밖에서 실행 | 프로젝트 루트로 이동 |
| `[ERROR] ... temperature는 0.0~1.0` | 범위 초과 | Anthropic 규격은 OpenAI(0~2)와 범위가 다릅니다 |
| `HTTP 401 인증 실패` | 키 오타 / 폐기된 키 | 콘솔에서 키 확인, 필요 시 재발급 |
| `HTTP 403 / 503 provider` | 기관에 provider 키 미등록 | 기관 운영자에게 문의 |
| `HTTP 429 요청 한도 초과` | 월 차감 토큰 소진 | 콘솔 [사용량] 탭 확인 |
| PR 본문 섹션이 비어 있음 | `max_tokens` 부족으로 절단 | `--max-tokens` 값을 늘리세요 |

---

## 10. 제약 사항

이 도구는 **초안 텍스트 출력까지**를 범위로 합니다.

- `git status`, `git diff` 범위의 정보만 수집합니다.
- `git commit`, `git push`, GitHub PR 생성(API 연동) 등 **원격 저장소에 반영하는 기능은 구현하지 않습니다.**
- 생성된 텍스트를 실제로 적용하는 것은 사용자의 판단과 책임입니다.
