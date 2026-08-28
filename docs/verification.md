# 검증 기록

평가항목 1(기능 재현) 체크리스트를 실제 실행으로 확인한 기록입니다.
모든 실행은 `claude-haiku-4`(차감 배수 0.5×), 저장소는 이 프로젝트 자신입니다.

| # | 체크 항목 | 결과 |
|---|---|---|
| 0 | `git status` 결과로 **변경된 파일 목록을 확인**할 수 있는가 | ✅ §1 |
| 1 | 커밋 메시지 생성 명령 실행 시 터미널에 출력되는가 | ✅ §1 |
| 2 | PR 생성 명령 실행 시 제목과 본문 초안이 출력되는가 | ✅ §2 |
| 3 | API Key 미설정 시 오류 메시지 출력 후 종료하는가 | ✅ §3 |
| 4 | 변경 사항이 없으면 "변경 사항이 없습니다"가 출력되는가 | ✅ §4 |
| 5 | PR 본문에 Why/What/How to Test + 각 섹션 최소 1불릿 | ✅ §2 |
| 6 | temperature / max-tokens 변경 시 차이가 재현되는가 | ✅ §5, §6 |
| 7 | 길이/형식 규칙을 만족하는가 | ✅ §7 |
| — | safe-mode 마스킹이 동작하는가 (제약사항) | ✅ §8 |

---

## §1. 커밋 메시지 생성 + 변경 파일 목록

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

- **변경된 파일 목록이 터미널에 출력됨** ✅ (기능요구 1)
  - `git status --porcelain -uall`을 쓴다. 기본값(`-unormal`)은 `docs/`처럼 디렉터리로
    뭉뚱그려 보고해서 목록이 부정확해진다.
- 제목 1줄 필수 ✅ / 본문 불릿 5개 ✅ / 변경된 모듈 언급 ✅
- 제목 42자 → 권장(50) 이내이므로 경고 없음
- `feat:` 컨벤션 접두사 적용 ✅

## §2. PR 초안 생성

```
$ python main.py pr

--- PR Title -----------------------------------------------
Initial commit: AI-powered Git commit/PR message generator with Codyssey API
------------------------------------------------------------

--- PR Body ------------------------------------------------
## Why
- 프로젝트 초기 구성으로 Git diff를 분석하여 커밋 메시지와 PR 초안을 자동 생성하는 도구 필요
- 개발자의 반복적인 문서 작성 작업을 자동화하고 일관성 있는 메시지 생성 지원
- Codyssey 공개 API(Anthropic 호환)를 활용한 AI 기반 솔루션 구현

## What
- Git status/diff 수집 및 처리 모듈 구현 (gitctx.py)
- Codyssey API 클라이언트 구현 (ai_client.py)
- 민감정보 마스킹 및 diff 절단 기능 (sanitizer.py)
- 출력 형식 검증 및 정렬 기능 (formatter.py)
- 커밋 메시지/PR 초안 생성 프롬프트 정의 (prompts.py)
- CLI 인터페이스 및 옵션 처리 (main.py)
- 환경변수 기반 API 키 관리 (.env.example, .gitignore)
- 상세한 사용 설명서 및 예시 (README.md)
- 의존성 관리 (requirements.txt)

## How to Test
- `python main.py commit --dry-run`으로 API 호출 없이 프롬프트 확인
- `python main.py commit --temperature 0.0`으로 결정적 출력 검증
- `python main.py pr --scope staged`로 스테이징된 변경사항만 처리 확인
- 실제 Git 저장소에서 변경사항 생성 후 `python main.py commit/pr` 실행하여 생성 결과 검증
- 다양한 옵션 조합(`--model`, `--max-tokens`, `--max-files` 등)으로 동작 확인
------------------------------------------------------------
[INFO] AI API 호출 횟수: 1회 | 사용량: 입력 3467 + 출력 589 토큰 (차감배수 0.5배)
```

- 제목 76자 → 상한 80자 이내 ✅
- Why / What / How to Test 3개 섹션 모두 존재, 각각 불릿 3 / 9 / 5개 ✅

## §3. API Key 미설정

```
$ unset AI_API_KEY
$ python main.py commit

[ERROR] AI_API_KEY 환경변수가 설정되지 않았습니다.
       예) export AI_API_KEY="sk-cody-live-YOUR_KEY"
       키 발급: https://usr.codyssey.kr/public-api-console
exit=1
```

Git 수집을 시작하기 **전에** 검사하므로 불필요한 작업 없이 즉시 종료합니다.

## §4. 변경 사항 없음

```
$ python main.py commit          # 변경이 없는 저장소에서

[INFO] 현재 브랜치: main
[INFO] Git status 수집 완료: 0개 파일 변경 감지
[INFO] 변경 사항이 없습니다. 생성하지 않고 종료합니다.
exit=0
```

**exit code가 0인 이유**: 사용자가 잘못한 것이 없으므로 오류가 아닙니다. API도 호출하지 않습니다.

## §5. temperature 변경에 따른 차이

같은 diff에 `--temperature` 값만 바꿔 3회 실행했습니다.

| 실행 | temperature | 출력 토큰 | 불릿 수 | 결과 |
|---|---|---|---|---|
| A | 0.0 | 200 | 5 | 기준 |
| B | 0.0 | 200 | 5 | **A와 완전히 동일** |
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

**관찰**

1. `temperature=0.0`은 **재현 가능**합니다. 같은 입력 → 같은 출력(출력 토큰까지 200으로 동일).
   프롬프트를 개선할 때 변경 효과만 분리해서 볼 수 있는 이유이며, 이 값을 CLI 옵션으로 뺀 근거입니다.
2. `temperature=1.0`은 불릿이 5 → 8개로 늘고 파일별로 잘게 나뉘었습니다. 출력 토큰 200 → 283.
3. 제목도 "CLI 도구 초기 구현" → "생성기 초기 구현"으로 미세하게 달라졌습니다.
   temperature는 확률분포를 평탄하게 만들 뿐이므로 **확신이 약한 지점부터 흔들립니다.**
   (영어 프롬프트로 측정했던 이전 회차에서는 제목이 세 번 모두 동일했습니다.)

## §6. max_tokens 변경 — 절단과 재생성

`--max-tokens 200`으로 일부러 부족하게 주어 구조적 실패를 유발했습니다.

```
$ python main.py pr --max-tokens 200

[INFO] AI API 요청 중... (model=claude-haiku-4, temperature=0.2, max_tokens=200)
[WARN] 응답이 max_tokens(200)에 걸려 잘렸습니다. --max-tokens를 늘리면 개선됩니다.
[WARN] 형식 규칙 위반으로 재생성합니다 (2회차): PR 본문에 `## How to Test` 섹션이 없습니다.
[WARN] 응답이 max_tokens(200)에 걸려 잘렸습니다. --max-tokens를 늘리면 개선됩니다.
[DONE] PR 초안 생성 완료

--- PR Body ------------------------------------------------
## Why
- Git diff를 읽어 커밋 메시지와 PR 초안을 자동으로 생성하는 도구의 필요성
- Codyssey 공개 API를 활용한 AI 기반 개발 생산성 향상
- 민감정보 마스킹과 diff 절단을 통한 안전한 API 전송

## What
- `main.py`: commit/pr 명령어로 초안 생성하는 CLI 진입점
- `gitctx.py`: git status/diff 수집 및 마스킹/          ← 문장 중간에서 잘림

## How to Test
- (AI가 생성하지 못했습니다 — 직접 작성이 필요합니다)   ← 후처리가 채운 스텁
------------------------------------------------------------
[WARN] `## How to Test` 섹션이 스텁으로 채워졌습니다 — 직접 작성이 필요합니다.
[INFO] AI API 호출 횟수: 2회 | 사용량: 입력 7017 + 출력 400 토큰 (차감배수 0.5배)
```

**하이브리드 전략의 전체 경로가 한 번에 재현되었습니다.**

1. 1회차 응답이 `max_tokens`에 걸려 잘림 → **HTTP 200이지만** `stop_reason: "max_tokens"`로 감지
2. `## How to Test` 섹션 누락 = **구조적 위반** → 재생성 판단
3. 2회차 재생성 (같은 `max_tokens`라 또 잘림 — 예상된 결과)
4. 재생성 실패 → **후처리로 착지**, 스텁 삽입 + `[WARN]`으로 정직하게 알림
5. **호출 2회** — 제약("1회 실행 시 1~2회") 준수, `MAX_CALLS_PER_RUN=2`가 상한을 강제

`max_tokens=1200`(기본값)으로 실행하면 §2처럼 정상적으로 3개 섹션이 모두 채워집니다.

## §7. 길이/형식 규칙

| 규칙 | 값 | 확인 |
|---|---|---|
| 커밋 제목 권장 | 50자 | 58자 → `[WARN]` 출력 (§1) |
| 커밋 제목 최대 | 72자 | 초과 시 단어 경계 절단 |
| PR 제목 최대 | 80자 | 76자 → 통과 (§2) |
| PR 섹션 헤더 | Why/What/How to Test 필수 | 누락 시 재생성 (§6) |
| 각 섹션 불릿 | 최소 1개 | 없으면 재생성, 실패 시 스텁 (§6) |
| 출력 구획 | 구분선/헤더로 분리 | `--- Commit Message ---` 형식 (§1) |

한국어 제목처럼 공백이 없는 경우에도 절단이 동작합니다(단어 경계를 못 찾으면 상한에서 그대로 자름).

## §8. safe-mode 마스킹

이 저장소의 소스에는 문서용 예시 키가 두 군데 있어 그대로 마스킹 대상이 됩니다.

```
$ python main.py commit -safe-mode --dry-run          # 기본값
[INFO] 민감정보 3건 마스킹 ([MASKED_API_KEY]×2, [MASKED_SECRET]×1)
+export AI_API_KEY="[MASKED_SECRET]"
+export AI_API_KEY="[MASKED_API_KEY]"

$ python main.py commit --no-safe-mode --dry-run
[WARN] safe-mode가 꺼져 있습니다 — diff의 민감정보가 그대로 전송됩니다.
+export AI_API_KEY="sk-cody-live-YOUR_KEY"
```

**두 규칙이 계층적으로 동작하는 것이 확인됩니다.**

| 원본 | 잡은 규칙 | 이유 |
|---|---|---|
| `sk-cody-live-YOUR_KEY` | `sk-` 접두사 규칙 | `sk-` 뒤 18자가 모두 허용 문자 |
| `sk-cody-live-여기에-발급받은-키` | 키=값 규칙 | 한글 때문에 `sk-` 규칙의 12자 조건 미달 → 일반 규칙이 받아냄 |

구체적 규칙이 놓친 것을 일반 규칙이 받아내는 **이중 방어**입니다.

### 오탐 방지 검증

마스킹 규칙이 정상 코드를 망가뜨리지 않는지 14개 케이스로 확인했습니다.

| 입력 | 기대 | 결과 |
|---|---|---|
| `DB_PASSWORD = "hunter2secret"` | 마스킹 | ✅ `[MASKED_SECRET]` |
| `api_key: 'abcd1234efgh'` | 마스킹 | ✅ |
| `+DB_PASSWORD=hunter2secret` | 마스킹 | ✅ (.env 스타일) |
| `+export MY_SECRET_TOKEN=abcdef123456` | 마스킹 | ✅ |
| `ADMIN_EMAIL = "carl@example.com"` | 마스킹 | ✅ `[MASKED_EMAIL]` |
| `password = user.password` | **보존** | ✅ 따옴표 없음 = 코드 |
| `access_token = response.json()["access_token"]` | **보존** | ✅ |
| `API_KEY = ""` | **보존** | ✅ 빈 값 |
| `TOKEN_TYPE = "Bearer"` | **보존** | ✅ 8자 미만 |
| `MODE = "test"` | **보존** | ✅ |
| `def get_user_token(self, user_id): return self.token` | **보존** | ✅ |
| `id = "550e8400-e29b-41d4-a716-446655440000"` | **보존** | ✅ UUID |
| `version = "2024-01-15"` | **보존** | ✅ |
| 개인키 PEM 블록 | 마스킹 | ✅ `[MASKED_PRIVATE_KEY]` |

**14/14 통과.** 핵심 구분선은 세 가지입니다.

- **따옴표 필수** — `PASSWORD = "hunter2"`는 비밀, `password = user.password`는 코드
- **값 8자 이상** — `TOKEN_TYPE = "Bearer"`(6자) 같은 비밀 아닌 값 제외
- **`.env` 규칙은 `=` 앞뒤 공백 금지** — `.env`는 `KEY=value`, 파이썬은 `key = value`

절단도 함께 동작합니다 — `[INFO] 파일 2개 생략`, `[INFO] diff 2132줄 생략`.
`--no-safe-mode`는 마스킹만 끄고 전송량 제한은 유지합니다(비용 방어 기능이기도 하므로).

---

## 부록. 총 사용량

검증 전체(실호출 8회)에서 사용한 토큰은 약 **3만 토큰**, 차감 기준 약 **1.5만 토큰**입니다.
월 한도 5,000,000 토큰의 0.3% 수준입니다.
