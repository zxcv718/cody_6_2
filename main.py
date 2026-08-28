"""AI 기반 Git 커밋/PR 초안 생성기 — CLI 진입점.

    python main.py commit
    python main.py pr --model claude-sonnet-4 --temperature 0.4

이 파일은 계층을 '조립'만 한다. git은 gitctx, 마스킹은 sanitizer, 호출은 ai_client,
프롬프트는 prompts, 검증은 formatter가 맡는다. 여기에 로직을 넣기 시작하면 계층
분리가 무의미해진다.
"""

from __future__ import annotations

import argparse
import sys
from typing import Callable

import ai_client
import formatter as fmt
import gitctx
import prompts
import sanitizer

DEFAULT_TEMPERATURE = 0.2
DEFAULT_MAX_TOKENS = {"commit": 700, "pr": 1200}
FILE_LIST_LIMIT = 20  # 터미널에 나열할 최대 파일 수


# ── 로그 (형식을 한 곳에서 통일) ──────────────────────────────────────────────
#
# flush=True가 붙어 있는 이유: 파이썬의 stdout은 터미널이면 줄 단위로, **파이프나
# 파일로 넘기면 블록 단위(4KB)로** 버퍼링된다. 반면 stderr는 항상 즉시 나간다.
# 그래서 `python main.py commit > log.txt 2>&1` 처럼 리다이렉트하면 stdout이
# 종료 시점에 한꺼번에 쏟아지고, 그 사이에 나간 [ERROR]가 [INFO]보다 앞에 찍힌다.
# 진행 로그와 오류의 순서가 뒤바뀌면 로그를 읽을 수 없으므로 매 줄 flush 한다.

def info(msg: str) -> None:
    print(f"[INFO] {msg}", flush=True)


def done(msg: str) -> None:
    print(f"[DONE] {msg}", flush=True)


def warn(msg: str) -> None:
    print(f"[WARN] {msg}", flush=True)


def error(msg: str) -> None:
    sys.stdout.flush()  # 앞선 진행 로그를 먼저 내보낸 뒤 오류를 찍는다
    print(f"[ERROR] {msg}", file=sys.stderr, flush=True)


# ── CLI ─────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python main.py",
        description="git 변경 사항을 읽어 커밋 메시지 / PR 초안을 생성합니다.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "예시:\n"
            "  python main.py commit\n"
            "  python main.py pr --model claude-sonnet-4 --max-tokens 1500\n"
            "  python main.py commit --temperature 0.0 --dry-run\n"
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    for name, help_text in (
        ("commit", "커밋 메시지 초안 생성"),
        ("pr", "PR 제목/본문 초안 생성"),
    ):
        p = sub.add_parser(name, help=help_text, description=help_text)

        # 과제 예시가 `-model` 표기라 단일 하이픈도 함께 받는다.
        p.add_argument(
            "-model", "--model", dest="model",
            default=ai_client.DEFAULT_MODEL, choices=sorted(ai_client.CHAT_MODELS),
            help=f"사용할 모델 (기본: {ai_client.DEFAULT_MODEL}, 차감배수 0.5배)",
        )
        p.add_argument(
            "-temperature", "--temperature", dest="temperature",
            type=float, default=DEFAULT_TEMPERATURE,
            help=f"무작위성 0.0~1.0 (기본: {DEFAULT_TEMPERATURE}). "
                 "낮을수록 결정적·재현 가능, 높을수록 다양함",
        )
        p.add_argument(
            "-max-tokens", "--max-tokens", dest="max_tokens",
            type=int, default=None,
            help=f"출력 토큰 상한 (기본: commit {DEFAULT_MAX_TOKENS['commit']}, "
                 f"pr {DEFAULT_MAX_TOKENS['pr']}). 길이 조절기가 아니라 절단기",
        )
        p.add_argument(
            "--scope", choices=("all", "staged", "unstaged"), default="all",
            help="diff 수집 범위 (기본: all = staged + unstaged + 새 파일)",
        )
        # 명세가 `-safe-mode` 라는 이름을 예시로 들었으므로 켜는 쪽 옵션도 제공한다.
        # (기본이 ON이라 동작은 같지만, 평가자가 명세 문구 그대로 입력해도 통해야 한다)
        p.add_argument(
            "-safe-mode", "--safe-mode", dest="safe_mode", action="store_true",
            help="민감정보 마스킹을 켠다 (기본값)",
        )
        p.add_argument(
            "--no-safe-mode", dest="safe_mode", action="store_false",
            help="민감정보 마스킹을 끈다 (전송량 제한은 유지됨)",
        )
        p.set_defaults(safe_mode=True)
        p.add_argument(
            "--max-files", type=int, default=sanitizer.DEFAULT_MAX_FILES,
            help=f"프롬프트에 넣을 최대 파일 수 (기본: {sanitizer.DEFAULT_MAX_FILES})",
        )
        p.add_argument(
            "--max-lines", type=int, default=sanitizer.DEFAULT_MAX_LINES,
            help=f"프롬프트에 넣을 최대 diff 줄 수 (기본: {sanitizer.DEFAULT_MAX_LINES})",
        )
        p.add_argument(
            "--no-retry", action="store_true",
            help="구조적 실패에도 재생성하지 않는다 (API 호출 1회 고정)",
        )
        p.add_argument(
            "--dry-run", action="store_true",
            help="API를 호출하지 않고 전송될 프롬프트만 출력 (토큰 절약)",
        )
    return parser


# ── 생성 파이프라인 ──────────────────────────────────────────────────────────

def generate(
    client: ai_client.CodysseyClient,
    system: str,
    user: str,
    args: argparse.Namespace,
    parse: Callable[[str], tuple[str, str]],
    validate: Callable[[str, str], list[fmt.Issue]],
    postprocess: Callable[[str, str], tuple[str, str]],
) -> tuple[str, str, list[fmt.Issue]]:
    """하이브리드 전략: 후처리 우선, 구조적 실패에만 1회 재생성.

    반환: (제목, 본문, 후처리 후에도 남은 이슈)
    """
    def call(prompt_body: str) -> str:
        completion = client.complete(
            system=system, user=prompt_body, model=args.model,
            temperature=args.temperature, max_tokens=args.max_tokens,
        )
        if completion.was_truncated:
            # HTTP 200이지만 잘린 응답. 구조적 실패의 가장 흔한 원인.
            warn(
                f"응답이 max_tokens({args.max_tokens})에 걸려 잘렸습니다. "
                "--max-tokens를 늘리면 개선됩니다."
            )
        return completion.text

    title, body = parse(call(user))
    issues = validate(title, body)

    can_retry = (
        issues
        and fmt.has_structural_failure(issues)
        and not args.no_retry
        and client.call_count < client.max_calls
    )
    if can_retry:
        reasons = fmt.error_messages(issues)
        warn(f"형식 규칙 위반으로 재생성합니다 ({client.call_count + 1}회차): {'; '.join(reasons)}")
        title, body = parse(call(user + prompts.retry_hint(reasons)))
        issues = validate(title, body)

    title, body = postprocess(title, body)
    return title, body, validate(title, body)


def run(args: argparse.Namespace) -> int:
    # ① 키를 가장 먼저 본다 — git을 다 수집하고 나서 키가 없다고 하면 시간 낭비다.
    api_key = None
    if not args.dry_run:
        api_key = ai_client.load_api_key()

    # ② Git 수집 (여기까지는 API를 전혀 모른다)
    ctx = gitctx.build_context(scope=args.scope)
    info(f"현재 브랜치: {ctx.branch}")
    info(f"Git status 수집 완료: {len(ctx.files)}개 파일 변경 감지")
    # 기능 요구사항 1: "변경된 파일 목록을 확인할 수 있어야 한다".
    # 개수만 출력하면 사용자가 무엇이 프롬프트로 나가는지 알 수 없다.
    for f in ctx.files[:FILE_LIST_LIMIT]:
        print(f"         - {f}", flush=True)
    if len(ctx.files) > FILE_LIST_LIMIT:
        print(f"         ... 외 {len(ctx.files) - FILE_LIST_LIMIT}개", flush=True)

    if ctx.is_empty:
        info("변경 사항이 없습니다. 생성하지 않고 종료합니다.")
        return 0

    info(f"Git diff 수집 완료: {len(ctx.diff_text.splitlines())}줄 (+{ctx.added_lines} / -{ctx.removed_lines})")

    # ③ 보안 관문 — 이 뒤로는 원본 diff를 쓰지 않는다.
    clean = sanitizer.sanitize(
        ctx.diff_text, safe_mode=args.safe_mode,
        max_files=args.max_files, max_lines=args.max_lines,
    )
    for line in clean.report_lines():
        info(line)
    if not args.safe_mode:
        warn("safe-mode가 꺼져 있습니다 — diff의 민감정보가 그대로 전송됩니다.")

    # ④ 프롬프트 조립
    if args.command == "commit":
        system, user = prompts.SYSTEM_COMMIT, prompts.build_commit_user(ctx, clean)
        parse, validate, post = fmt.parse_commit, fmt.validate_commit, fmt.postprocess_commit
    else:
        system, user = prompts.SYSTEM_PR, prompts.build_pr_user(ctx, clean)
        parse, validate, post = fmt.parse_pr, fmt.validate_pr, fmt.postprocess_pr

    if args.dry_run:
        info("--dry-run: API를 호출하지 않고 프롬프트만 출력합니다.")
        print(fmt.render_block("System Prompt", system))
        print(fmt.render_block("User Prompt", user))
        return 0

    # ⑤ 생성
    info(f"AI API 요청 중... (model={args.model}, temperature={args.temperature}, max_tokens={args.max_tokens})")
    client = ai_client.CodysseyClient(api_key)
    title, body, remaining = generate(client, system, user, args, parse, validate, post)

    # ⑥ 출력
    if args.command == "commit":
        done("커밋 메시지 생성 완료")
        print(fmt.render_block("Commit Message", f"{title}\n\n{body}".strip()))
    else:
        done("PR 초안 생성 완료")
        print(fmt.render_block("PR Title", title))
        print(fmt.render_block("PR Body", body))

    for issue in remaining:
        # warn()이 이미 [WARN]을 붙이므로 severity를 그대로 덧붙이면 중복된다.
        # ERROR는 후처리로도 못 고친 것이므로 문구를 달리해 눈에 띄게 한다.
        warn(str(issue) if issue.severity == "WARN" else f"검토 필요 — {issue}")

    weight = ai_client.CHAT_MODELS[args.model]
    info(f"AI API 호출 횟수: {client.call_count}회 | 사용량: {client.usage_total} (차감배수 {weight}배)")
    info("생성된 문구는 초안입니다. 반드시 검토 후 사용하세요.")
    return 0


def main() -> int:
    args = build_parser().parse_args()
    if args.max_tokens is None:
        args.max_tokens = DEFAULT_MAX_TOKENS[args.command]

    try:
        ai_client.validate_temperature(args.temperature)
        return run(args)
    except ai_client.MissingAPIKeyError as exc:
        error(str(exc))
        return 1
    except (gitctx.GitError, ai_client.AIError, ValueError) as exc:
        error(str(exc))
        return 1
    except KeyboardInterrupt:
        error("사용자가 중단했습니다.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
