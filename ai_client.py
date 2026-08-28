"""API 계층 — Codyssey 게이트웨이(Anthropic 규격) 호출만 담당한다.

이 모듈은 git도 커밋 메시지도 모른다. "시스템 프롬프트 + 사용자 프롬프트를 주면
텍스트를 돌려준다"가 전부다. 프롬프트의 *내용*은 prompts.py, 결과의 *형식 검증*은
formatter.py의 일이다.

Codyssey는 자체 모델이 아니라 프록시다. 규격을 그대로 중계하기 때문에 base_url만
바꾸면 진짜 Anthropic API로도 그대로 동작한다. 그래서 base_url을 환경변수로 뺐다.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

import requests

DEFAULT_BASE_URL = "https://copa.codyssey.kr"
ANTHROPIC_VERSION = "2023-06-01"

# 콘솔 "모델별 차감 가중치" 표의 CHAT 모델 중 Anthropic 규격(/v1/messages)으로
# 호출 가능한 것들. 값은 월 한도에서 깎이는 배수다.
CHAT_MODELS: dict[str, float] = {
    "claude-haiku-4": 0.5,    # Claude Haiku 4.5  — 개발/반복 테스트 기본값
    "claude-sonnet-4": 1.0,   # Claude Sonnet 4.6 — 최종 결과물 품질
    "claude-opus-4-7": 1.5,   # Claude Opus 4.7
    "claude-opus-4-8": 1.5,   # Claude Opus 4.8
}
DEFAULT_MODEL = "claude-haiku-4"

# 과제 제약: "1회 실행 시 요청 횟수는 1~2회 이내". 이 상수가 곧 재생성 예산이다.
MAX_CALLS_PER_RUN = 2

# Anthropic 규격의 temperature 범위. OpenAI(0.0~2.0)와 다르다.
TEMPERATURE_MIN, TEMPERATURE_MAX = 0.0, 1.0


class AIError(RuntimeError):
    """API 호출 실패. 메시지에 항상 '원인'이 들어 있어야 한다."""


class MissingAPIKeyError(AIError):
    pass


class CallBudgetExceeded(AIError):
    pass


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0

    def __str__(self) -> str:
        return f"입력 {self.input_tokens} + 출력 {self.output_tokens} 토큰"


@dataclass
class Completion:
    text: str
    stop_reason: str  # end_turn / max_tokens / stop_sequence / tool_use
    usage: Usage

    @property
    def was_truncated(self) -> bool:
        """max_tokens에 걸려 잘렸는가.

        중요: 잘려도 HTTP 200이다. 에러가 아니라 '조용한 실패'라서 이 플래그를
        보지 않으면 섹션이 사라진 응답을 정상으로 착각한다.
        """
        return self.stop_reason == "max_tokens"


def load_api_key() -> str:
    """환경변수에서 키를 읽는다. 코드에 하드코딩하지 않는다는 제약의 실행 지점."""
    key = os.environ.get("AI_API_KEY") or os.environ.get("CODYSSEY_API_KEY")
    if not key or not key.strip():
        raise MissingAPIKeyError(
            "AI_API_KEY 환경변수가 설정되지 않았습니다.\n"
            '       예) export AI_API_KEY="sk-cody-live-YOUR_KEY"\n'
            "       키 발급: https://usr.codyssey.kr/public-api-console"
        )
    return key.strip()


def validate_temperature(value: float) -> float:
    """Anthropic 규격은 0.0~1.0. 넘기면 서버가 400을 준다 — 그 전에 여기서 잡는다."""
    if not TEMPERATURE_MIN <= value <= TEMPERATURE_MAX:
        raise ValueError(
            f"temperature는 {TEMPERATURE_MIN}~{TEMPERATURE_MAX} 사이여야 합니다 "
            f"(입력값: {value}). Anthropic 규격은 OpenAI(0.0~2.0)와 범위가 다릅니다."
        )
    return value


class CodysseyClient:
    """호출 1건 = 메서드 1회. 호출 횟수를 스스로 세고 예산을 넘으면 거부한다."""

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        timeout: float = 60.0,
        max_calls: int = MAX_CALLS_PER_RUN,
    ) -> None:
        self.api_key = api_key
        self.base_url = (
            base_url or os.environ.get("CODYSSEY_BASE_URL") or DEFAULT_BASE_URL
        ).rstrip("/")
        self.timeout = timeout
        self.max_calls = max_calls
        self.call_count = 0
        self.usage_total = Usage()

    def complete(
        self,
        *,
        system: str,
        user: str,
        model: str = DEFAULT_MODEL,
        temperature: float = 0.2,
        max_tokens: int = 700,
    ) -> Completion:
        if self.call_count >= self.max_calls:
            raise CallBudgetExceeded(
                f"이번 실행의 API 호출 예산({self.max_calls}회)을 모두 사용했습니다."
            )

        payload = {
            "model": model,
            "max_tokens": max_tokens,  # Anthropic 규격에서 필수
            "temperature": validate_temperature(temperature),
            "system": system,          # messages 안이 아니라 최상위 필드
            "messages": [{"role": "user", "content": user}],
        }
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        }

        self.call_count += 1
        try:
            resp = requests.post(
                f"{self.base_url}/v1/messages",
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )
        except requests.Timeout as exc:
            raise AIError(
                f"AI API 응답 시간 초과 ({self.timeout:.0f}초). "
                "diff가 너무 크면 --max-lines를 줄여 보세요."
            ) from exc
        except requests.ConnectionError as exc:
            raise AIError(
                f"AI API 서버에 연결할 수 없습니다 ({self.base_url}). "
                "네트워크 연결과 base URL을 확인하세요."
            ) from exc
        except requests.RequestException as exc:
            raise AIError(f"AI API 요청 실패: {exc}") from exc

        if resp.status_code != 200:
            raise _map_http_error(resp)

        return self._parse(resp)

    def _parse(self, resp: requests.Response) -> Completion:
        try:
            data = resp.json()
        except json.JSONDecodeError as exc:
            raise AIError(
                f"AI API 응답을 JSON으로 해석할 수 없습니다: {resp.text[:200]}"
            ) from exc

        blocks = data.get("content") or []
        # content[0]["text"]로 첫 블록을 하드코딩하지 않는다.
        # thinking·tool_use 블록이 섞이면 인덱스 0이 텍스트가 아니다.
        text = "".join(
            b.get("text", "") for b in blocks if isinstance(b, dict) and b.get("type") == "text"
        )
        if not text.strip():
            raise AIError(
                f"AI 응답에 텍스트 블록이 없습니다 (stop_reason={data.get('stop_reason')}). "
                "max_tokens를 늘려 보세요."
            )

        raw_usage = data.get("usage") or {}
        usage = Usage(
            input_tokens=raw_usage.get("input_tokens", 0),
            output_tokens=raw_usage.get("output_tokens", 0),
        )
        self.usage_total.input_tokens += usage.input_tokens
        self.usage_total.output_tokens += usage.output_tokens

        return Completion(
            text=text.strip(),
            stop_reason=data.get("stop_reason", "unknown"),
            usage=usage,
        )


def _map_http_error(resp: requests.Response) -> AIError:
    """HTTP 오류를 '무엇이 왜 실패했는지'가 담긴 메시지로 바꾼다.

    게이트웨이는 provider에 없던 실패 모드를 새로 만든다(403/409). 내 키는 멀쩡한데
    기관의 provider 키가 없어서 실패하는 경우가 있어, 상태 코드별 안내가 특히 중요하다.
    """
    try:
        detail = (resp.json().get("error") or {}).get("message") or resp.text[:300]
    except (json.JSONDecodeError, AttributeError):
        detail = resp.text[:300]

    guides = {
        400: "요청 형식 오류입니다. (Anthropic 규격은 max_tokens 필수, temperature 0.0~1.0)",
        401: "인증 실패 — API 키가 잘못되었거나 폐기되었습니다. 콘솔에서 키를 확인하세요.",
        403: "권한 없음 — 소속 기관에 해당 provider 키가 등록되지 않았을 수 있습니다. 운영자에게 문의하세요.",
        404: f"엔드포인트를 찾을 수 없습니다. base URL({resp.url})을 확인하세요.",
        429: "요청 한도 초과 — 월 차감 토큰이 소진되었거나 호출이 너무 잦습니다. 콘솔 사용량 탭을 확인하세요.",
        503: "게이트웨이가 provider 자격증명을 사용할 수 없습니다. 잠시 후 재시도하거나 운영자에게 문의하세요.",
    }
    guide = guides.get(resp.status_code, "예상하지 못한 오류입니다.")
    return AIError(f"AI API 오류 [HTTP {resp.status_code}] {guide}\n       서버 응답: {detail}")
