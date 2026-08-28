"""출력 계층 — 코드가 '강제'하는 곳.

prompts.py는 AI에게 부탁한다(보장 없음). 이 모듈은 코드로 강제한다(보장 있음).

핵심 설계: 규칙 위반을 두 종류로 나눈다.

  양적 위반   제목이 80자다 / 마크다운 펜스로 감쌌다 / 따옴표가 붙었다
              → 정답이 유일하게 결정된다. 자르고 벗기면 끝. **후처리**.
                 재생성하면 토큰만 쓰고 결과는 같거나 더 나쁘다.

  구조적 위반 `## How to Test` 섹션이 통째로 없다
              → 헤더는 만들 수 있어도 *내용*이 없다. 형식 문제가 아니라 정보 부족이라
                 코드로 못 만든다. **재생성**만이 해법.

재생성은 최대 1회. 예산을 넘으면 후처리로 착지한다 — 확률적 시스템에서 재시도는
반드시 상한과 결정적 fallback이 함께 있어야 한다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from prompts import PR_BODY_MARKER, PR_SECTIONS, PR_TITLE_MARKER

COMMIT_TITLE_SOFT = 50  # 권장
COMMIT_TITLE_HARD = 72  # 최대
PR_TITLE_MAX = 80

# 후처리가 빈 섹션을 채울 때 쓰는 문구. validate가 이걸 알아보고 경고를 남긴다.
STUB_TEXT = "(AI가 생성하지 못했습니다 — 직접 작성이 필요합니다)"

_FENCE = re.compile(r"^\s*```[a-zA-Z]*\s*\n(.*?)\n?\s*```\s*$", re.S)
_BULLET = re.compile(r"^\s*[-*•]\s+\S")

# Conventional Commits 접두사. 명세 필수는 아니지만 결과 예시가 `feat:` 형태이고,
# 프롬프트로 지시한 것이 실제로 지켜졌는지 확인하는 용도다.
# WARN이지 ERROR가 아니다 — 재생성 트리거가 아니며, 없어도 출력은 유효하다.
COMMIT_TYPES = ("feat", "fix", "docs", "refactor", "test", "chore", "style", "perf", "build", "ci")
_TYPE_PREFIX = re.compile(rf"^({'|'.join(COMMIT_TYPES)})(\([^)]+\))?!?:\s+\S")


@dataclass
class Issue:
    message: str
    structural: bool = False  # True면 재생성 트리거
    severity: str = "ERROR"   # ERROR | WARN

    def __str__(self) -> str:
        return self.message


def has_structural_failure(issues: list[Issue]) -> bool:
    return any(i.structural for i in issues)


def error_messages(issues: list[Issue]) -> list[str]:
    """재생성 힌트로 넘길 메시지 (경고는 제외 — 경고까지 재생성할 이유는 없다)."""
    return [i.message for i in issues if i.severity == "ERROR"]


# ── 정리 유틸 ────────────────────────────────────────────────────────────────

def strip_fence(text: str) -> str:
    """응답 전체를 감싼 ```코드블록```을 벗긴다."""
    m = _FENCE.match(text.strip())
    return m.group(1) if m else text.strip()


def clean_title(text: str) -> str:
    """제목 한 줄을 다듬는다. 마크다운 헤더·따옴표·끝 마침표 제거."""
    t = text.strip()
    t = re.sub(r"^#{1,6}\s*", "", t)          # ## 제목
    t = re.sub(r'^["\'`]+|["\'`]+$', "", t)   # 감싼 따옴표
    t = re.sub(r"\s+", " ", t).strip()
    return t.rstrip(".")


def truncate_at_word(text: str, limit: int) -> str:
    """단어 경계에서 자른다. 경계를 못 찾으면 그냥 자른다(한국어처럼 붙어 쓰는 경우)."""
    if len(text) <= limit:
        return text
    head = text[: limit - 1]
    cut = head.rfind(" ")
    if cut > limit * 0.6:  # 너무 앞에서 끊기면 차라리 통째로 자른다
        head = head[:cut]
    return head.rstrip(" ,.-") + "…"


def _split_sections(body: str) -> dict[str, list[str]]:
    """`## 헤더` 기준으로 본문을 섹션별 줄 목록으로 나눈다."""
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in body.splitlines():
        m = re.match(r"^\s*#{2,3}\s*(.+?)\s*$", line)
        if m:
            current = m.group(1).strip()
            sections[current] = []
        elif current is not None:
            sections[current].append(line)
    return sections


def _find_section(sections: dict[str, list[str]], name: str) -> list[str] | None:
    """헤더 이름을 느슨하게 찾는다 (`## Why (변경 배경)` 같은 변형 허용)."""
    target = name.lower().replace(" ", "")
    for key, lines in sections.items():
        if key.lower().replace(" ", "").startswith(target):
            return lines
    return None


# ── commit ──────────────────────────────────────────────────────────────────

def parse_commit(raw: str) -> tuple[str, str]:
    """AI 응답에서 (제목, 본문)을 뽑는다. 첫 줄이 제목이라는 계약."""
    text = strip_fence(raw)
    lines = [l for l in text.splitlines()]
    while lines and not lines[0].strip():
        lines.pop(0)
    if not lines:
        return "", ""
    title = clean_title(lines[0])
    body = "\n".join(lines[1:]).strip()
    return title, body


def validate_commit(title: str, body: str) -> list[Issue]:
    issues: list[Issue] = []
    if not title:
        issues.append(Issue("커밋 제목이 비어 있습니다.", structural=True))
        return issues
    if len(title) > COMMIT_TITLE_HARD:
        issues.append(Issue(f"커밋 제목이 {len(title)}자입니다. {COMMIT_TITLE_HARD}자 이내로 줄이세요."))
    elif len(title) > COMMIT_TITLE_SOFT:
        issues.append(
            Issue(f"커밋 제목이 {len(title)}자입니다 (권장 {COMMIT_TITLE_SOFT}자 이내).", severity="WARN")
        )
    if not _TYPE_PREFIX.match(title):
        issues.append(
            Issue(f"제목에 컨벤션 접두사가 없습니다 (예: {', '.join(COMMIT_TYPES[:4])}).",
                  severity="WARN")
        )
    if body and not any(_BULLET.match(l) for l in body.splitlines()):
        # 본문은 선택이지만, 있다면 불릿 1개 이상이어야 한다는 과제 최소 기준.
        issues.append(Issue("커밋 본문에 `- ` 불릿이 하나도 없습니다.", structural=True))
    return issues


def postprocess_commit(title: str, body: str) -> tuple[str, str]:
    title = truncate_at_word(clean_title(title), COMMIT_TITLE_HARD)
    body = "\n".join(l.rstrip() for l in body.splitlines()).strip()
    return title, body


# ── pr ──────────────────────────────────────────────────────────────────────

def parse_pr(raw: str) -> tuple[str, str]:
    """`<<<TITLE>>> / <<<BODY>>>` 계약으로 파싱한다.

    마커가 없으면 폴백: 첫 줄을 제목으로, 나머지를 본문으로 본다. 형식이 조금 어긋나도
    사용자에게 아무것도 못 보여주는 것보다는 낫다.
    """
    text = strip_fence(raw)
    if PR_TITLE_MARKER in text and PR_BODY_MARKER in text:
        head, _, rest = text.partition(PR_TITLE_MARKER)
        title_part, _, body_part = rest.partition(PR_BODY_MARKER)
        return clean_title(title_part), body_part.strip()

    lines = [l for l in text.splitlines() if l.strip()]
    if not lines:
        return "", ""
    # 폴백 시 첫 `##` 헤더부터를 본문으로 본다.
    for i, l in enumerate(lines):
        if l.lstrip().startswith("##"):
            return clean_title(lines[0]), "\n".join(lines[i:]).strip()
    return clean_title(lines[0]), "\n".join(lines[1:]).strip()


def validate_pr(title: str, body: str) -> list[Issue]:
    issues: list[Issue] = []
    if not title:
        issues.append(Issue("PR 제목이 비어 있습니다.", structural=True))
    elif len(title) > PR_TITLE_MAX:
        issues.append(Issue(f"PR 제목이 {len(title)}자입니다. {PR_TITLE_MAX}자 이내로 줄이세요."))
    elif not _TYPE_PREFIX.match(title):
        issues.append(
            Issue(f"PR 제목에 컨벤션 접두사가 없습니다 (예: {', '.join(COMMIT_TYPES[:4])}).",
                  severity="WARN")
        )

    sections = _split_sections(body)
    for name in PR_SECTIONS:
        lines = _find_section(sections, name)
        if lines is None:
            # 섹션 자체가 없음 → 코드로 내용을 만들 수 없다 → 재생성.
            issues.append(Issue(f"PR 본문에 `## {name}` 섹션이 없습니다.", structural=True))
        elif not any(_BULLET.match(l) for l in lines):
            issues.append(Issue(f"`## {name}` 섹션에 불릿이 하나도 없습니다.", structural=True))
        elif any(STUB_TEXT in l for l in lines):
            # 후처리가 채운 스텁. 형식은 통과하지만 내용이 없으므로 사용자에게 알린다.
            # structural=False — 이미 재생성을 시도한 뒤의 착지점이라 또 재생성할 이유가 없다.
            issues.append(
                Issue(f"`## {name}` 섹션이 스텁으로 채워졌습니다 — 직접 작성이 필요합니다.",
                      severity="WARN")
            )
    return issues


def postprocess_pr(title: str, body: str) -> tuple[str, str]:
    """재생성으로도 못 고쳤을 때의 착지점. 없는 섹션은 스텁으로 채운다.

    스텁은 좋은 결과가 아니다. 하지만 '형식이 깨진 채 출력'보다는 낫고,
    사용자에게 `[WARN]`으로 무엇이 비었는지 함께 알린다.
    """
    title = truncate_at_word(clean_title(title), PR_TITLE_MAX)
    sections = _split_sections(body)

    rebuilt: list[str] = []
    for name in PR_SECTIONS:
        lines = _find_section(sections, name)
        content = [l for l in (lines or []) if l.strip()]
        if not any(_BULLET.match(l) for l in content):
            content.append(f"- {STUB_TEXT}")
        rebuilt.append(f"## {name}")
        rebuilt.extend(content)
        rebuilt.append("")
    return title, "\n".join(rebuilt).strip()


# ── 렌더링 ───────────────────────────────────────────────────────────────────

def render_block(heading: str, content: str, width: int = 60) -> str:
    """구분선/헤더로 구획을 나눠 출력한다 (과제: 사용자가 검토할 수 있도록)."""
    top = f"--- {heading} " + "-" * max(3, width - len(heading) - 5)
    return f"\n{top}\n{content}\n{'-' * len(top)}"
