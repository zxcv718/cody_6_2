"""Git 변경 사항 수집 계층.

이 모듈은 AI API를 전혀 모른다. 로컬 git 명령을 실행해 `GitContext` 하나를 만드는
것까지가 책임이다.

수집(로컬·결정적·무료)과 API 호출(원격·확률적·유료)은 실패 원인도 재시도 정책도
완전히 다르다. 한 함수에 섞으면 "git이 실패했나 API가 실패했나"를 가릴 수 없고,
API 키 없이 수집만 테스트하는 것도 불가능해진다. 그래서 계층을 나눈다.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field

# `git status --porcelain`의 XY 코드 → 사람이 읽는 라벨
_STATUS_LABEL = {
    "M": "수정",
    "A": "추가",
    "D": "삭제",
    "R": "이름변경",
    "C": "복사",
    "U": "충돌",
    "?": "미추적",
}


class GitError(RuntimeError):
    """git 명령 실행 자체가 실패했을 때. (변경이 없는 것은 오류가 아니다)"""


@dataclass
class ChangedFile:
    index_status: str  # 스테이징 영역 상태 (X)
    work_status: str  # 작업 트리 상태 (Y)
    path: str
    old_path: str | None = None  # 이름 변경 시 원래 경로

    @property
    def label(self) -> str:
        """`git status`의 두 글자 코드를 한국어 한 단어로. 우선순위는 index > worktree."""
        code = self.index_status if self.index_status not in " ?" else self.work_status
        return _STATUS_LABEL.get(code, code)

    @property
    def is_untracked(self) -> bool:
        return self.index_status == "?" and self.work_status == "?"

    def __str__(self) -> str:
        if self.old_path:
            return f"{self.label}: {self.old_path} -> {self.path}"
        return f"{self.label}: {self.path}"


@dataclass
class GitContext:
    """AI에게 넘길 재료. 이 객체를 만든 뒤로는 git을 더 호출하지 않는다."""

    branch: str
    files: list[ChangedFile] = field(default_factory=list)
    diff_text: str = ""
    added_lines: int = 0
    removed_lines: int = 0
    has_commits: bool = True  # False면 이번이 최초 커밋

    @property
    def is_empty(self) -> bool:
        return not self.files and not self.diff_text.strip()

    def file_summary(self) -> str:
        """프롬프트에 넣을 변경 파일 목록 (diff보다 먼저 읽히도록 간결하게)."""
        return "\n".join(f"- {f}" for f in self.files)


def git_raw(*args: str, cwd: str | None = None) -> subprocess.CompletedProcess[str]:
    """git을 실행하고 CompletedProcess를 그대로 돌려준다.

    returncode가 필요한 호출자를 위한 저수준 함수. 성공/실패를 stdout의 내용으로
    판단하면 안 되는 경우가 있기 때문에 존재한다 — 예를 들어 커밋이 없는 저장소에서
    `git rev-parse --abbrev-ref HEAD`는 실패하면서도 stdout에 "HEAD"를 출력한다.
    """
    try:
        return subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError as exc:
        raise GitError("git이 설치되어 있지 않거나 PATH에 없습니다.") from exc


def run_git(*args: str, cwd: str | None = None, check: bool = True) -> str:
    """git 명령을 실행하고 stdout을 반환한다.

    check=False는 "0이 아닌 종료 코드가 정상인 경우"에 쓴다.
    대표적으로 `git diff --no-index`는 차이가 있으면 1을 반환한다.
    """
    proc = git_raw(*args, cwd=cwd)
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip()
        raise GitError(f"git {' '.join(args)} 실패: {detail}")
    return proc.stdout


def ensure_repo(cwd: str | None = None) -> None:
    """Git 저장소 안에서 실행 중인지 확인. 아니면 GitError."""
    try:
        inside = run_git("rev-parse", "--is-inside-work-tree", cwd=cwd).strip()
    except GitError as exc:
        raise GitError(
            "Git 저장소가 아닙니다. Git이 초기화된 프로젝트 루트에서 실행하세요."
        ) from exc
    if inside != "true":
        raise GitError("Git 작업 트리가 아닙니다 (bare 저장소일 수 있습니다).")


def current_branch(cwd: str | None = None) -> str:
    """현재 브랜치명.

    `symbolic-ref`를 쓴다. "HEAD가 브랜치를 가리키나, 어느 것인가"를 **커밋 존재 여부와
    무관하게** 답해주기 때문이다.

    `rev-parse --abbrev-ref HEAD`를 쓰면 안 된다: 커밋이 하나도 없는 저장소에서
    실패하면서도 stdout에 "HEAD"를 출력해서, 갓 만든 저장소를 detached HEAD로
    오판하게 만든다. (returncode를 안 보고 stdout만 보면 놓치는 함정)
    """
    proc = git_raw("symbolic-ref", "--short", "HEAD", cwd=cwd)
    if proc.returncode == 0 and proc.stdout.strip():
        return proc.stdout.strip()

    # HEAD가 브랜치를 가리키지 않음 = 진짜 detached HEAD
    short = git_raw("rev-parse", "--short", "HEAD", cwd=cwd)
    if short.returncode == 0 and short.stdout.strip():
        return f"(detached HEAD @ {short.stdout.strip()})"
    return "(unknown)"


def has_commits(cwd: str | None = None) -> bool:
    """커밋이 하나라도 있는가. 없으면 이번이 최초 커밋이다."""
    return git_raw("rev-parse", "--verify", "HEAD", cwd=cwd).returncode == 0


def collect_status(cwd: str | None = None) -> list[ChangedFile]:
    """`git status --porcelain`을 파싱해 변경 파일 목록을 만든다.

    -z 를 쓰는 이유: 공백·따옴표가 든 경로를 git이 이스케이프해서 내보내는 것을 피하려면
    NUL 구분 출력을 쓰는 편이 안전하다.
    """
    # -uall: 미추적 항목을 디렉터리로 뭉뚱그리지 않고 파일 단위로 나열한다.
    # 기본값(-unormal)은 `docs/`처럼 디렉터리만 보고해서 목록이 부정확해진다.
    raw = run_git("status", "--porcelain", "-uall", "-z", cwd=cwd)
    tokens = raw.split("\0")
    files: list[ChangedFile] = []

    i = 0
    while i < len(tokens):
        entry = tokens[i]
        i += 1
        if len(entry) < 3:
            continue
        index_status, work_status, path = entry[0], entry[1], entry[3:]
        old_path = None
        # 이름 변경/복사는 원래 경로가 '다음' NUL 토큰으로 따로 온다.
        if index_status in ("R", "C"):
            old_path = tokens[i] if i < len(tokens) else None
            i += 1
        files.append(ChangedFile(index_status, work_status, path, old_path))
    return files


def _untracked_diff(path: str, cwd: str | None = None) -> str:
    """추적되지 않은 새 파일의 diff를 만든다.

    `git diff`는 untracked 파일을 아예 보지 않는다. `git add -N`으로 인덱스에 등록하면
    보이게 되지만, 그건 사용자의 저장소 상태를 조용히 바꾸는 짓이라 읽기 전용 도구가
    할 일이 아니다. `--no-index`는 부작용 없이 같은 결과를 낸다.

    주의: `--no-index`는 차이가 있으면 종료 코드 1을 반환한다(정상). check=False 필수.
    """
    return run_git(
        "diff", "--no-index", "--", "/dev/null", path, cwd=cwd, check=False
    )


def collect_diff(cwd: str | None = None, scope: str = "all") -> str:
    """변경 내용(diff 텍스트)을 수집한다.

    scope:
      staged   — `git diff --cached` (실제 커밋될 내용과 정확히 일치)
      unstaged — `git diff`
      all      — 둘 다 + untracked 파일 (기본값)

    기본값이 all인 이유: `git add` 없이 파일만 고치고 바로 실행해도 동작해야 시연이
    안전하다. 실무 정확성(staged만)보다 재현성을 택한 절충이다.
    """
    parts: list[str] = []

    if scope in ("staged", "all"):
        staged = run_git("diff", "--cached", cwd=cwd)
        if staged.strip():
            parts.append(staged)

    if scope in ("unstaged", "all"):
        unstaged = run_git("diff", cwd=cwd)
        if unstaged.strip():
            parts.append(unstaged)

    if scope == "all":
        for f in collect_status(cwd):
            if f.is_untracked:
                chunk = _untracked_diff(f.path, cwd=cwd)
                if chunk.strip():
                    parts.append(chunk)

    return "\n".join(parts)


def count_line_changes(diff_text: str) -> tuple[int, int]:
    """diff에서 추가/삭제 줄 수를 센다. 파일 헤더(+++/---)는 제외한다."""
    added = removed = 0
    for line in diff_text.splitlines():
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            added += 1
        elif line.startswith("-"):
            removed += 1
    return added, removed


def build_context(cwd: str | None = None, scope: str = "all") -> GitContext:
    """수집 계층의 단일 진입점. 여기서 나온 GitContext만 상위 계층으로 넘어간다."""
    ensure_repo(cwd)
    files = collect_status(cwd)
    if scope == "staged":
        files = [f for f in files if f.index_status not in " ?"]
    elif scope == "unstaged":
        files = [f for f in files if f.work_status != " "]

    diff_text = collect_diff(cwd, scope)
    added, removed = count_line_changes(diff_text)
    return GitContext(
        branch=current_branch(cwd),
        has_commits=has_commits(cwd),
        files=files,
        diff_text=diff_text,
        added_lines=added,
        removed_lines=removed,
    )
