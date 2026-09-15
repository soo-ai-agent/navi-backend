from __future__ import annotations

from decimal import Decimal
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock

from app.dto.response.next_step import NextStepResponseDTO
from app.dto.response.question import QuestionResponseDTO
from app.dto.response.ranking import RankedSavingResponseDTO, RankingResultResponseDTO
from app.enums.answer_kind import AnswerKind
from app.enums.saving import MonthlyLimitStatus
from app.enums.saving import InterestCalcType, ReserveType
from app.dto.response.wish import WishRankedSavingResponseDTO
from app.external.llm.wish_reply_writer import WishReplyWriter
from app.model.vo.unmapped_wish_vo import UnmappedWishVO
from app.model.vo.wish_structure_vo import WishStructureVO


def _structured() -> WishStructureVO:
    return WishStructureVO(
        answers=(), unmapped=(UnmappedWishVO(name="앱 사용 편의성", text="앱이 편한"),),
    )


def _ranked_row() -> RankedSavingResponseDTO:
    return RankedSavingResponseDTO(
        product_id="p1", rank=1, bank_name="테스트은행", product_name="튼튼적금",
        rate=Decimal("3.5"), base_rate=Decimal("3.0"), max_rate=Decimal("4.0"),
        reserve_type=ReserveType.FIXED, interest_calc_type=InterestCalcType.SIMPLE,
        saving_term_months=12, monthly_limit_status=MonthlyLimitStatus.UNLIMITED, monthly_limit=0,
        bonus_condition_text="", bonus_results=(), other_conditions=(),
        other_eligibility_conditions=(), other_bonus_conditions=(),
    )


class TestWishReplyWriter(IsolatedAsyncioTestCase):
    async def write(
            self, step: NextStepResponseDTO, ranked: tuple[WishRankedSavingResponseDTO, ...] = (),
    ) -> tuple[str, str]:
        """(LLM 답변, LLM 에게 준 사실 목록)을 돌려준다."""
        llm_client = AsyncMock()
        llm_client.ask_json.return_value = '{"reply": "답변 문장"}'
        reply = await WishReplyWriter(llm_client).write(_structured(), step, ranked)
        facts: str = llm_client.ask_json.call_args.args[0][1].content
        return reply, facts

    async def test_다음_질문과_보존_요구를_사실로_전달한다(self):
        question = QuestionResponseDTO(
            key="months", title="얼마 동안 넣을까요?", answer_kind=AnswerKind.OPTIONS,
            options=(("12", "12개월"),),
        )
        reply, facts = await self.write(NextStepResponseDTO.of_question(question))
        self.assertEqual("답변 문장", reply)
        self.assertIn("다음 질문: 얼마 동안 넣을까요?", facts)
        self.assertIn("선택지: 12개월", facts)
        self.assertIn("반영하지 못한 요구: 앱 사용 편의성", facts)

    async def test_확정_순위를_사실로_전달한다(self):
        result = RankingResultResponseDTO(rows=(_ranked_row(),))
        ranked = (WishRankedSavingResponseDTO(**dict(_ranked_row()), reason="금리가 가장 높다"),)
        _reply, facts = await self.write(NextStepResponseDTO.of_result(result), ranked)
        self.assertIn("1위: 테스트은행 튼튼적금, 금리 연 3.5% (12개월) — 금리가 가장 높다", facts)
