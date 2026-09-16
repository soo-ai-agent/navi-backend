from __future__ import annotations
import time
from typing import TYPE_CHECKING
import httpx
from app.external.llm.exception import LlmApiError
from app.external.llm.model import ChatRequest, ChatResponse
from infra.request_context import short_request_id

if TYPE_CHECKING:
    from logging import Logger
    from typing import Sequence

    from app.external.llm.model import ChatMessage

_CHAT_PATH = "/chat/completions"

_REASONING_EFFORT = "medium"
"""솔라의 추론 강도. 우대조건 구조화는 문장을 쪼개는 일이라 중간이면 충분하다"""


class LlmClient:
    _base_url: str
    _api_key: str
    _model: str
    _logger: Logger

    def __init__(self, base_url: str, api_key: str, model: str, logger: Logger) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._logger = logger

    async def ask_json(
            self, messages: Sequence[ChatMessage], max_tokens: int = 4096,
            reasoning_effort: str = _REASONING_EFFORT, purpose: str = "일반",
    ) -> str:
        url: str = f"{self._base_url}{_CHAT_PATH}"
        payload: ChatRequest = ChatRequest(
            model=self._model, messages=tuple(messages),
            reasoning_effort=reasoning_effort, max_tokens=max_tokens,
        )
        input_chars: int = sum(len(message.content) for message in messages)
        self._logger.info(
            "LLM 호출 시작 | req=%s | 목적=%s | model=%s | effort=%s | 입력chars=%d",
            short_request_id(), purpose, self._model, reasoning_effort, input_chars,
        )
        started: float = time.monotonic()

        # Upstage 응답에는 고정 제한을 두지 않는다. timeout=None은 httpx에서 무제한 대기를 뜻하는 설정값이다.
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                response: httpx.Response = await client.post(
                    url, content=payload.model_dump_json(),
                    headers=(("Authorization", f"Bearer {self._api_key}"), ("Content-Type", "application/json"))
                )
        except httpx.HTTPError as error:
            # 연결 실패도 어떤 호출이었는지 남긴다 — 처리는 못 하므로 기록만 하고 그대로 올린다.
            self._logger.error(
                "LLM 호출 실패 | req=%s | 목적=%s | 오류=%s | 소요ms=%d",
                short_request_id(), purpose, type(error).__name__, _elapsed_ms(started),
            )
            raise

        if response.status_code != httpx.codes.OK:
            self._logger.error(
                "LLM 호출 실패 | req=%s | 목적=%s | status=%d | 소요ms=%d",
                short_request_id(), purpose, response.status_code, _elapsed_ms(started),
            )
            raise LlmApiError.from_response(response)

        result: ChatResponse = ChatResponse.model_validate_json(response.content)
        content: str = result.choices[0].message.content
        self._logger.info(
            "LLM 호출 완료 | req=%s | 목적=%s | status=%d | 응답chars=%d | 소요ms=%d | 토큰=%s",
            short_request_id(), purpose, response.status_code, len(content), _elapsed_ms(started),
            result.usage.summary() if result.usage else "미제공",
        )
        return content


def _elapsed_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)
