from __future__ import annotations
from typing import TYPE_CHECKING
from pydantic import BaseModel, ConfigDict, Field
from app.constants.wish_rank_prompt import WISH_RANK_PROMPT
from app.external.llm import ChatMessage

if TYPE_CHECKING:
    from app.dto.response.next_step import NextStepResponseDTO
    from app.external.llm import LlmClient
    from app.model.vo.banks_vo import BanksVO
    from app.model.vo.saving_rate import SavingRate
    from app.model.vo.unmapped_wish_vo import UnmappedWishVO

_SOURCE_TEXT_SIZE = 150
"""상품마다 프롬프트에 싣는 공시 원문 길이. 근거 인용에 충분한 만큼만 싣는다"""

_RANK_MAX_TOKENS = 16384
"""순위 응답 토큰 한도. 추론 토큰 + 상품 근거 문장이 4096 기본값을 넘는다"""

_RANK_REASONING_EFFORT = "low"
"""순위 추론 강도. medium 은 후보 20개에 5분 넘게 걸려 대화 응답으로 못 쓴다"""


class RankedWishItem(BaseModel):
    """LLM 이 정한 순위 한 줄. 이 수신 경계에서만 쓴다."""

    model_config = ConfigDict(frozen=True)

    product_id: str
    reason: str = Field(max_length=300)


class WishRankReply(BaseModel):
    """LLM 이 한 호출로 돌려주는 순위와 답변 문장. 호출 횟수를 줄여 응답 시간을 아낀다."""

    model_config = ConfigDict(frozen=True)

    rankings: tuple[RankedWishItem, ...]
    reply: str


class WishLlmRanker:
    """사용자 상황을 읽어 상품 순서와 답변 문장을 정한다. 금리·조건 계산은 하지 않는다."""

    _llm_client: LlmClient

    def __init__(self, llm_client: LlmClient) -> None:
        self._llm_client = llm_client

    async def rank(
            self, message: str, candidates: tuple[SavingRate, ...], banks: BanksVO,
            step: NextStepResponseDTO, unmapped: tuple[UnmappedWishVO, ...],
    ) -> WishRankReply:
        answer: str = await self._llm_client.ask_json((
            ChatMessage(role="system", content=WISH_RANK_PROMPT),
            ChatMessage(role="user", content=self._facts(message, candidates, banks, step, unmapped)),
        ), max_tokens=_RANK_MAX_TOKENS, reasoning_effort=_RANK_REASONING_EFFORT)
        return WishRankReply.model_validate_json(answer)

    @staticmethod
    def _facts(
            message: str, candidates: tuple[SavingRate, ...], banks: BanksVO,
            step: NextStepResponseDTO, unmapped: tuple[UnmappedWishVO, ...],
    ) -> str:
        """LLM 에게 줄 사실 목록. 상품마다 판정된 금리와 공시 원문만 적는다."""
        lines: list[str] = [f"사용자 문장: {message}", "", "상품 목록:"]
        for candidate in candidates:
            join_member: str = candidate.saving.join_member[:_SOURCE_TEXT_SIZE]
            bonus_text: str = candidate.saving.bonus_condition_text[:_SOURCE_TEXT_SIZE]
            lines.append(
                f"- product_id={candidate_id(candidate)}"
                f" | {banks.name(candidate.saving.bank_code)} {candidate.saving.name}"
                f" | 금리 연 {candidate.rate}% ({candidate.option.saving_term_months}개월)"
                f" | 가입대상: {join_member}"
                f" | 우대조건: {bonus_text}"
            )

        if step.question is not None:
            lines.append(f"다음 질문: {step.question.title}")
            labels: str = ", ".join(label for _value, label in step.question.options)
            if labels:
                lines.append(f"선택지: {labels}")

        for item in unmapped:
            lines.append(f"상품 데이터에 없어 비교에 반영하지 못한 요구: {item.name}")

        return "\n".join(lines)


def candidate_id(candidate: SavingRate) -> str:
    """LLM 과 주고받는 후보 식별자. 같은 상품이라도 기간이 다르면 다른 후보다."""
    return f"{candidate.saving.product_id}@{candidate.option.saving_term_months}"
