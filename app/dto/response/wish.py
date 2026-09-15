from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.dto.response.next_step import NextStepResponseDTO
from app.dto.response.ranking import RankedSavingResponseDTO
from app.model.vo.saving_rate import SavingRate
from app.model.vo.wish_structure_vo import WishStructureVO


class WishRankedSavingResponseDTO(RankedSavingResponseDTO):
    """순위에 오른 상품 한 건 + 왜 이 순서인지 사용자에게 보여줄 근거."""

    reason: str

    @classmethod
    def from_rate_with_reason(
            cls, rate: SavingRate, rank: int, bank_name: str, reason: str,
    ) -> WishRankedSavingResponseDTO:
        base: RankedSavingResponseDTO = RankedSavingResponseDTO.from_rate(rate, rank, bank_name)
        return cls(**dict(base), reason=reason)


class WishAnswerResponseDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: str
    """question.code — 질문 흐름(/questions/next)에 그대로 실을 수 있는 키"""
    value: str


class UnmappedWishResponseDTO(BaseModel):
    """상품 데이터로 판정할 수 없어 원문 그대로 보존한 요구."""

    model_config = ConfigDict(frozen=True)

    name: str
    text: str


class WishResponseDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    wish_id: int | None
    """이번 턴에 새 문장을 저장했을 때의 번호. 버튼으로만 답한 턴에는 저장한 문장이 없다"""

    reply: str
    """구조화·판정 결과를 사용자에게 말하는 문장. 버튼 답 턴은 빈 문자열 — 프론트가 질문을 그린다"""

    next: NextStepResponseDTO
    """질문 흐름의 판정 결과 원본 — 다음 질문 또는 확정 순위"""

    ranked: tuple[WishRankedSavingResponseDTO, ...]
    """사용자 상황에 맞춰 LLM 이 정한 순위. 금리·조건 값은 규칙 엔진 계산값 그대로다"""

    answers: tuple[WishAnswerResponseDTO, ...]
    unmapped: tuple[UnmappedWishResponseDTO, ...]

    @classmethod
    def from_structured(
            cls, wish_id: int | None, structured: WishStructureVO, reply: str, step: NextStepResponseDTO,
            ranked: tuple[WishRankedSavingResponseDTO, ...],
    ) -> WishResponseDTO:
        return cls(
            wish_id=wish_id,
            reply=reply,
            next=step,
            ranked=ranked,
            answers=tuple(
                WishAnswerResponseDTO(code=answer.code, value=answer.value) for answer in structured.answers
            ),
            unmapped=tuple(
                UnmappedWishResponseDTO(name=item.name, text=item.text) for item in structured.unmapped
            ),
        )
