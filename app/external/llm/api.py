from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

from app.external.llm.exception import LlmApiError
from app.external.llm.model import ChatRequest, ChatResponse

if TYPE_CHECKING:
    from typing import Sequence

    from app.external.llm.model import ChatMessage

_CHAT_PATH = "/chat/completions"

_REASONING_EFFORT = "medium"
"""솔라의 추론 강도. 우대조건 구조화는 문장을 쪼개는 일이라 중간이면 충분하다"""


class LlmClient:
    _base_url: str
    _api_key: str
    _model: str

    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model

    async def ask_json(
            self, messages: Sequence[ChatMessage], max_tokens: int = 4096,
            reasoning_effort: str = _REASONING_EFFORT,
    ) -> str:
        url: str = f"{self._base_url}{_CHAT_PATH}"
        payload: ChatRequest = ChatRequest(
            model=self._model, messages=tuple(messages),
            reasoning_effort=reasoning_effort, max_tokens=max_tokens,
        )

        # Upstage 응답에는 고정 제한을 두지 않는다. timeout=None은 httpx에서 무제한 대기를 뜻하는 설정값이다.
        async with httpx.AsyncClient(timeout=None) as client:
            response: httpx.Response = await client.post(
                url, content=payload.model_dump_json(),
                headers=(("Authorization", f"Bearer {self._api_key}"), ("Content-Type", "application/json"))
            )

        if response.status_code != httpx.codes.OK:
            raise LlmApiError.from_response(response)

        result: ChatResponse = ChatResponse.model_validate_json(response.content)
        return result.choices[0].message.content
