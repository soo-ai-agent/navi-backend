from __future__ import annotations
from pydantic import BaseModel, ConfigDict
from app.model.vo.unmapped_wish_vo import UnmappedWishVO
from app.model.vo.wish_answer_vo import WishAnswerVO


class WishStructureVO(BaseModel):
    """사용자 문장을 구조화한 결과. LLM 응답을 검증해 만든다."""

    model_config = ConfigDict(frozen=True)

    answers: tuple[WishAnswerVO, ...]
    unmapped: tuple[UnmappedWishVO, ...]

    def keep_known(self, codes: frozenset[str]) -> WishStructureVO:
        """LLM 이 지어낸 질문 코드의 답을 매핑하지 않고 unmapped 로 옮긴다."""
        known: list[WishAnswerVO] = []
        moved: list[UnmappedWishVO] = []

        for answer in self.answers:
            if answer.code in codes:
                known.append(answer)
            else:
                moved.append(UnmappedWishVO(name=answer.code, text=answer.value))

        return WishStructureVO(answers=tuple(known), unmapped=self.unmapped + tuple(moved))
