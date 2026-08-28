"""보안 계층 — 외부로 나가는 diff의 단일 관문.

`git diff`에는 `.env` 수정, 하드코딩된 키, 테스트 픽스처의 개인정보가 섞일 수 있다.
프롬프트에 "민감정보는 빼고 보내"라고 쓰는 건 *부탁*이고 보장이 없다. 조립 직전에
반드시 통과해야 하는 함수를 하나 두는 것이 *강제*다.

관문이 하나여야 하는 이유: 마스킹 함수가 여러 개면 "어떤 경로로도 원본이 새지 않는다"를
반증할 수 없다. 보안 코드는 우회 경로가 0개임을 코드 구조로 보여야 한다.
그래서 상위 계층은 diff를 절대 직접 만지지 않고 `sanitize()`의 결과만 사용한다.

두 가지를 동시에 한다.
  (A) 마스킹  — 민감해 보이는 패턴을 자리표시자로 치환
  (B) 절단    — 파일 수·줄 수 상한을 걸어 전송량(=비용)과 노출면을 함께 줄인다
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# 절단 기본값. CLI 옵션으로 덮어쓸 수 있다.
DEFAULT_MAX_FILES = 10
DEFAULT_MAX_LINES = 200


# ─────────────────────────────────────────────────────────────────────────────
# 마스킹 규칙
#
# `(정규식, 치환문자열)` 튜플의 리스트. **위에서부터 순서대로** 적용된다.
#
# 설계 기준 — 과제 명세에 구체적 목록이 없어 다음 원칙으로 자체 판단했다.
#
#   1. 구조가 뚜렷해 오탐이 낮은 것부터 잡는다.
#      `sk-`, `ghp_`, `AKIA` 같은 발급 기관이 정한 접두사는 우연히 일치할 일이 거의 없다.
#      반대로 "비밀번호처럼 생긴 문자열"을 잡으려 하면 코드 전체가 마스킹된다.
#
#   2. 치환문자열에 **종류를 남긴다**. `[MASKED]`가 아니라 `[MASKED_EMAIL]`로 쓰면
#      AI가 "이메일 관련 변경이구나"를 알 수 있어 요약 품질이 유지된다.
#      가리는 것은 값이지 맥락이 아니다.
#
#   3. 키=값 형태에서는 **값만** 가리고 키 이름은 남긴다.
#      `API_KEY = "[MASKED_SECRET]"`은 설정 변경임을 알 수 있지만,
#      줄 전체를 가리면 AI가 무슨 변경인지 알 수 없다.
#
#   4. 구체적 규칙을 일반 규칙보다 앞에 둔다.
#      `API_KEY = "sk-..."`는 ①에서 `[MASKED_API_KEY]`가 되고,
#      뒤따르는 일반 KV 규칙은 lookahead로 이미 마스킹된 값을 건너뛴다.
#
# 트레이드오프: 넓게 잡으면 diff가 자리표시자 범벅이 되어 AI가 변경 내용을 이해하지
# 못하고, 좁게 잡으면 진짜 비밀이 새어 나간다. 아래는 "구조가 있는 비밀"과 "형식이
# 정해진 개인정보"만 잡는 쪽으로 균형을 잡은 것이다.
#
# ⚠️ 한계: 정규식은 **형식이 있는 것만** 잡는다. 내부 서버 주소, 사람 이름, 사업 로직
#    같은 비정형 비밀은 잡을 수 없다. 마스킹은 최후 방어선이 아니라 안전망이며,
#    근본 대책은 애초에 비밀을 커밋하지 않는 것이다.
# ─────────────────────────────────────────────────────────────────────────────

MASK_RULES: list[tuple[re.Pattern[str], str]] = [
    # ── ① 개인키 블록 (여러 줄) ────────────────────────────────────────────
    (
        re.compile(
            r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
            re.S,
        ),
        "[MASKED_PRIVATE_KEY]",
    ),

    # ── ② 발급 기관이 정한 접두사를 가진 키·토큰 (오탐 거의 없음) ──────────
    # OpenAI / Anthropic / Codyssey
    (re.compile(r"\bsk-[A-Za-z0-9_-]{12,}"), "[MASKED_API_KEY]"),
    # GitHub personal access token / OAuth
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{16,}"), "[MASKED_GITHUB_TOKEN]"),
    # AWS Access Key ID
    (re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"), "[MASKED_AWS_KEY]"),
    # Google API key
    (re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"), "[MASKED_GOOGLE_KEY]"),
    # Slack token
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}"), "[MASKED_SLACK_TOKEN]"),
    # JWT (header.payload.signature — base64url 3토막)
    (
        re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"),
        "[MASKED_JWT]",
    ),

    # ── ③ 키=값 형태의 비밀 (②에서 안 걸린 나머지) ─────────────────────────
    #
    # 핵심 판별 기준: **값이 문자열 리터럴인가.**
    #   PASSWORD = "hunter2"        → 비밀 (마스킹)
    #   password = user.password    → 그냥 코드 (건드리지 않음)
    # 따옴표를 필수로 요구하면 이 둘이 깔끔하게 갈린다. 따옴표 없이 잡으려 하면
    # `access_token = response.json()["access_token"]` 같은 코드까지 망가뜨린다.
    #
    # 키 이름 앞뒤에 `[A-Za-z0-9_]*`를 허용하는 이유: `\b`만 쓰면 `_`가 단어 문자라
    # `DB_PASSWORD`에서 `\bpassword\b`가 매칭되지 않는다.
    (
        re.compile(
            r"""(?ix)
            \b( [A-Za-z0-9_]*
               (?: pass(?:word|wd)? | secret | token | credential
                 | api[_-]?key | access[_-]?key | private[_-]?key )
               [A-Za-z0-9_]* )
            (\s*[:=]\s*)
            (["'])                  # 여는 따옴표 — 필수
            (?!\[MASKED)
            [^"'\n]{8,}             # 값 (8자 이상)
                                   # 4가 아니라 8인 이유: TOKEN_TYPE="Bearer"(6),
                                   # MODE="test"(4) 같은 비밀 아닌 값을 걸러낸다.
                                   # 8자 미만 비밀은 놓치지만, 과마스킹으로 diff를
                                   # 못 읽게 만드는 쪽이 더 해롭다고 판단.
            \3                      # 닫는 따옴표
            """
        ),
        r"\1\2\3[MASKED_SECRET]\3",
    ),

    # ── ③-b .env 스타일 (따옴표 없는 KEY=VALUE) ────────────────────────────
    # diff 줄은 `+`/`-`/` `로 시작하므로 그것까지 포함해 줄 앞부터 매칭한다.
    (
        re.compile(
            r"""(?imx)
            ^([+\-\ ]?\s* (?:export\s+)?
              [A-Za-z0-9_]*
              (?: PASS(?:WORD|WD)? | SECRET | TOKEN | CREDENTIAL
                | API_?KEY | ACCESS_?KEY | PRIVATE_?KEY )
              [A-Za-z0-9_]* =)      # `=` 앞뒤에 공백이 없어야 한다
                                    # .env 는 KEY=value, 파이썬은 key = value.
                                    # 이 한 글자 차이가 설정 파일과 코드를 가른다.
            (?!["'\s]|\[MASKED)      # 따옴표는 위 규칙이 담당, 빈 값 제외
            [^\s#]{8,}               # 값
            """
        ),
        r"\1[MASKED_SECRET]",
    ),

    # ── ④ 형식이 정해진 개인정보 ───────────────────────────────────────────
    # 주민등록번호 (뒷자리 첫 숫자는 1~4 또는 5~8)
    (re.compile(r"\b\d{6}-[1-8]\d{6}\b"), "[MASKED_RRN]"),
    # 신용카드 번호 (4-4-4-4). UUID(8-4-4-4-12)와 자릿수가 달라 충돌하지 않는다.
    (re.compile(r"\b\d{4}[- ]\d{4}[- ]\d{4}[- ]\d{4}\b"), "[MASKED_CARD]"),
    # 한국 휴대폰 번호
    (re.compile(r"\b01[016789][- ]?\d{3,4}[- ]?\d{4}\b"), "[MASKED_PHONE]"),
    # 이메일
    (
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
        "[MASKED_EMAIL]",
    ),
]


@dataclass
class SanitizeResult:
    """무엇을 어떻게 가렸는지 호출자가 알 수 있어야 한다 — 조용히 고치지 않는다."""

    text: str
    masked_count: int = 0
    masked_kinds: list[str] = field(default_factory=list)
    total_files: int = 0
    kept_files: int = 0
    dropped_lines: int = 0

    @property
    def dropped_files(self) -> int:
        return max(0, self.total_files - self.kept_files)

    def report_lines(self) -> list[str]:
        """CLI가 `[INFO]`로 출력할 요약. 아무것도 안 했으면 빈 리스트."""
        out: list[str] = []
        if self.masked_count:
            kinds = ", ".join(self.masked_kinds)
            out.append(f"민감정보 {self.masked_count}건 마스킹 ({kinds})")
        if self.dropped_files:
            out.append(f"파일 {self.dropped_files}개 생략 (상한 초과)")
        if self.dropped_lines:
            out.append(f"diff {self.dropped_lines}줄 생략 (상한 초과)")
        return out


# 치환문자열에서 `[MASKED_*]` 부분만 뽑아내기 위한 패턴.
# 일부 규칙의 치환문자열은 `\1\2\3[MASKED_SECRET]\3`처럼 역참조를 포함하는데,
# 그대로 로그에 찍으면 사용자에게 정규식 내부가 노출된다.
_PLACEHOLDER = re.compile(r"\[MASKED_[A-Z_]*\]")


def apply_masks(text: str) -> tuple[str, int, list[str]]:
    """MASK_RULES를 순서대로 적용한다. (마스킹된 텍스트, 건수, 적용된 종류)"""
    total = 0
    counts: dict[str, int] = {}
    for pattern, replacement in MASK_RULES:
        text, n = pattern.subn(replacement, text)
        if n:
            total += n
            m = _PLACEHOLDER.search(replacement)
            label = m.group(0) if m else replacement
            counts[label] = counts.get(label, 0) + n
    return text, total, [f"{k}×{v}" for k, v in counts.items()]


def split_by_file(diff_text: str) -> list[str]:
    """`diff --git` 경계로 diff를 파일 단위 청크로 자른다.

    파일 단위로 잘라야 절단해도 각 청크가 유효한 diff 조각으로 남는다.
    그냥 200줄에서 싹둑 자르면 마지막 파일의 헤더만 남고 내용이 없는 꼴이 될 수 있다.
    """
    if not diff_text.strip():
        return []
    chunks: list[str] = []
    current: list[str] = []
    for line in diff_text.splitlines():
        if line.startswith("diff --git") and current:
            chunks.append("\n".join(current))
            current = []
        current.append(line)
    if current:
        chunks.append("\n".join(current))
    return chunks


def truncate_diff(
    diff_text: str,
    max_files: int = DEFAULT_MAX_FILES,
    max_lines: int = DEFAULT_MAX_LINES,
) -> tuple[str, int, int, int]:
    """파일 수·줄 수 상한을 적용한다.

    반환: (잘린 diff, 전체 파일 수, 남긴 파일 수, 생략된 줄 수)

    줄 예산은 전체에 대해 걸린다. 파일별로 걸면 파일이 많을 때 총량이 폭발한다.
    """
    chunks = split_by_file(diff_text)
    total_files = len(chunks)
    if not chunks:
        return diff_text, 0, 0, 0

    kept: list[str] = []
    budget = max_lines
    dropped = 0

    for chunk in chunks[:max_files]:
        lines = chunk.splitlines()
        if budget <= 0:
            dropped += len(lines)
            continue
        if len(lines) > budget:
            kept.append("\n".join(lines[:budget]))
            kept.append(f"... (이 파일의 나머지 {len(lines) - budget}줄 생략)")
            dropped += len(lines) - budget
            budget = 0
        else:
            kept.append(chunk)
            budget -= len(lines)

    for chunk in chunks[max_files:]:
        dropped += len(chunk.splitlines())

    return "\n".join(kept), total_files, min(total_files, max_files), dropped


def sanitize(
    diff_text: str,
    safe_mode: bool = True,
    max_files: int = DEFAULT_MAX_FILES,
    max_lines: int = DEFAULT_MAX_LINES,
) -> SanitizeResult:
    """단일 관문. 프롬프트 조립 전 diff는 반드시 이 함수를 통과한다.

    safe_mode=False여도 절단은 유지한다 — 절단은 보안 기능이자 비용 방어 기능이라,
    끄면 큰 저장소에서 토큰이 폭주한다. safe_mode가 끄는 것은 '마스킹'뿐이다.
    """
    text, total_files, kept_files, dropped = truncate_diff(diff_text, max_files, max_lines)

    masked_count = 0
    kinds: list[str] = []
    if safe_mode:
        text, masked_count, kinds = apply_masks(text)

    return SanitizeResult(
        text=text,
        masked_count=masked_count,
        masked_kinds=kinds,
        total_files=total_files,
        kept_files=kept_files,
        dropped_lines=dropped,
    )
