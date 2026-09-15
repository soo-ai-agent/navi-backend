from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from app.constants.wish_reply_prompt import WISH_REPLY_PROMPT
from app.external.llm import ChatMessage

if TYPE_CHECKING:
    from app.dto.response.next_step import NextStepResponseDTO
    from app.dto.response.wish import WishRankedSavingResponseDTO
    from app.external.llm import LlmClient
    from app.model.vo.wish_structure_vo import WishStructureVO

_INTRODUCE_SIZE = 3
"""말로 소개할 상품 수. 전체 순위는 응답의 next.result 로 따로 내려간다"""


class _WishReply(BaseModel):
    """LLM 답변 JSON 의 모양. 이 수신 경계에서만 쓴다."""

    model_config = ConfigDict(frozen=True)

    reply: str


class WishReplyWriter:
    """Python 이 판정한 결과(다음 질문·추천 순위)를 자연스러운 말로 옮긴다."""

    _llm_client: LlmClient

    def __init__(self, llm_client: LlmClient) -> None:
        self._llm_client = llm_client

    async def write(
            self, structured: WishStructureVO, step: NextStepResponseDTO,
            ranked: tuple[WishRankedSavingResponseDTO, ...],
    ) -> str:
        answer: str = await self._llm_client.ask_json((
            ChatMessage(role="system", content=WISH_REPLY_PROMPT),
            ChatMessage(role="user", content=self._facts(structured, step, ranked)),
        ))
        return _WishReply.model_validate_json(answer).reply

    @staticmethod
    def _facts(
            structured: WishStructureVO, step: NextStepResponseDTO,
            ranked: tuple[WishRankedSavingResponseDTO, ...],
    ) -> str:
        """LLM 에게 줄 사실 목록. 지어낼 여지를 없애려 판정된 값만 적는다."""
        lines: list[str] = []

        if step.question is not None:
            lines.append(f"다음 질문: {step.question.title}")
            labels: str = ", ".join(label for _value, label in step.question.options)
            if labels:
                lines.append(f"선택지: {labels}")

        for row in ranked[:_INTRODUCE_SIZE]:
            lines.append(
                f"{row.rank}위: {row.bank_name} {row.product_name},"
                f" 금리 연 {row.rate}% ({row.saving_term_months}개월) — {row.reason}"
            )

        for item in structured.unmapped:
            lines.append(f"상품 데이터에 없어 비교에 반영하지 못한 요구: {item.name}")

        return "\n".join(lines)
