from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.constants.saving_condition_prompt import SAVING_CONDITION_PROMPT
from app.external.llm import ChatMessage
from app.model.vo.extracted_conditions_vo import ExtractedConditionsVO
from app.model.vo.saving_condition_source_vo import SavingConditionSourceVO
from app.external.llm.exception import ConditionLlmParseError
from app.external.llm.condition_response import normalize_condition_response

if TYPE_CHECKING:
    from app.external.llm import LlmClient

_CONDITION_MAX_TOKENS = 16384
"""조건 구조화 응답 토큰 한도. 추론 토큰이 4096 기본값을 다 쓰면 본문 없이 잘린다"""


@dataclass(frozen=True)
class ConditionParseResult:
    raw_response: str
    extracted: ExtractedConditionsVO


class ConditionLlmParser:
    _llm_client: LlmClient

    def __init__(self, llm_client: LlmClient) -> None:
        self._llm_client = llm_client

    async def parse(self, source: SavingConditionSourceVO) -> ConditionParseResult:
        schema: str = json.dumps(ExtractedConditionsVO.model_json_schema(), ensure_ascii=False)
        messages: tuple[ChatMessage, ...] = (
            ChatMessage(role="system", content=SAVING_CONDITION_PROMPT + "\n" + schema),
            ChatMessage(role="user", content=source.model_dump_json()),
        )
        answer: str = await self._llm_client.ask_json(messages, max_tokens=_CONDITION_MAX_TOKENS)
        try:
            normalized_answer: str = normalize_condition_response(answer)
            received: ExtractedConditionsVO = ExtractedConditionsVO.model_validate_json(normalized_answer)
            extracted: ExtractedConditionsVO = received.with_source_status(source)
            extracted.verify(source)
        except Exception as error:
            raise ConditionLlmParseError(answer, error) from error
        return ConditionParseResult(raw_response=answer, extracted=extracted)
