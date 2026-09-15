from __future__ import annotations

import json
from typing import TYPE_CHECKING

from app.constants.wish_prompt import WISH_PROMPT
from app.external.llm import ChatMessage
from app.model.vo.wish_structure_vo import WishStructureVO

if TYPE_CHECKING:
    from typing import Sequence

    from app.external.llm import LlmClient
    from app.model.database.question import Question

_PARSE_MAX_TOKENS = 16384
"""구조화 응답 토큰 한도. 추론 토큰이 4096 기본값을 다 쓰면 본문 없이 잘린다"""


class WishLlmParser:
    _llm_client: LlmClient

    def __init__(self, llm_client: LlmClient) -> None:
        self._llm_client = llm_client

    async def parse(self, message: str, questions: Sequence[Question]) -> WishStructureVO:
        schema: str = json.dumps(WishStructureVO.model_json_schema(), ensure_ascii=False)
        question_lines: str = "\n".join(
            f"- {question.code}: {question.title} ({question.answer_kind.value})" for question in questions
        )
        prompt: str = f"{WISH_PROMPT}\n질문 목록(code: 질문, 답 형식):\n{question_lines}\n{schema}"

        answer: str = await self._llm_client.ask_json((
            ChatMessage(role="system", content=prompt),
            ChatMessage(role="user", content=message),
        ), max_tokens=_PARSE_MAX_TOKENS)
        structured: WishStructureVO = WishStructureVO.model_validate_json(answer)

        codes: frozenset[str] = frozenset(question.code for question in questions)
        return structured.keep_known(codes)
