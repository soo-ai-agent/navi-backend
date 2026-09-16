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

_REPLY_REASONING_EFFORT = "minimal"
"""안내문은 판정된 사실을 옮겨 적는 일이라 추론이 필요 없다 — medium 18초대가 minimal 1초대로 준다"""


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
            ranked: tuple[WishRankedSavingResponseDTO, ...], message: str = "",
    ) -> str:
        # message 기본값 빈 문자열: 관리자 단건 시험(llm_test) 경로에는 사용자 발화가 없다.
        answer: str = await self._llm_client.ask_json((
            ChatMessage(role="system", content=WISH_REPLY_PROMPT),
            ChatMessage(role="user", content=self._facts(structured, step, ranked, message)),
        ), reasoning_effort=_REPLY_REASONING_EFFORT, purpose="안내문")
        return _WishReply.model_validate_json(answer).reply

    @staticmethod
    def _facts(
            structured: WishStructureVO, step: NextStepResponseDTO,
            ranked: tuple[WishRankedSavingResponseDTO, ...], message: str,
    ) -> str:
        """LLM 에게 줄 사실 목록. 지어낼 여지를 없애려 판정된 값만 적는다."""
        lines: list[str] = []

        # 사용자가 밝힌 상황(직업·신분·목적)을 첫마디에 받아줄 수 있게 발화 원문을 준다.
        if message:
            lines.append(f"사용자가 방금 한 말: {message}")

        if step.question is not None:
            lines.append(f"다음 질문: {step.question.title}")
            # 선택지는 화면 버튼으로 보이므로 reply 에 나열되지 않게 아예 주지 않는다.

        for row in ranked[:_INTRODUCE_SIZE]:
            lines.append(
                f"{row.rank}위: {row.bank_name} {row.product_name},"
                f" 금리 연 {row.rate}% ({row.saving_term_months}개월) — {row.reason}"
            )

        # 항목별로 줄을 나누면 LLM 이 같은 문형을 반복하므로 한 줄로 묶어 준다.
        if structured.unmapped:
            names: str = ", ".join(item.name for item in structured.unmapped)
            lines.append(f"상품 데이터에 없어 비교에 반영하지 못한 요구: {names}")

        return "\n".join(lines)
