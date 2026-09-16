"""문장 순위 병합 검증 — LLM 이 지어낸 후보는 버리고, 빠뜨린 후보는 금리 순서로 보충한다."""

from __future__ import annotations
import logging
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock
from app.dto.response.next_step import NextStepResponseDTO
from app.dto.response.ranking import RankingResultResponseDTO
from app.external.llm.wish_ranker import RankedWishItem, WishLlmRanker, WishRankReply, candidate_id
from app.model.vo.answer_vo import AnswerVO
from app.model.vo.answers_vo import AnswersVO
from app.model.vo.banks_vo import BanksVO
from app.model.vo.saving_products_vo import SavingProductsVO
from app.model.database.bank import Bank
from app.service.wish.wish_ranking import WishRanking, WishRankingService
from app.source.banks_source import BanksSource
from app.source.saving_products_source import SavingProductsSource
from test.service.saving.saving_fixture import group, predicate, saving


def _service(products: SavingProductsVO, reply: WishRankReply) -> WishRankingService:
    savings_source = AsyncMock(spec=SavingProductsSource)
    savings_source.get.return_value = products
    banks_source = AsyncMock(spec=BanksSource)
    banks_source.get.return_value = BanksVO(banks=(
        Bank(bank_code="bank", original_name="은행", display_name="은행",
             homepage_url="https://bank.example", call_center="1588-0000"),
    ))
    ranker = AsyncMock(spec=WishLlmRanker)
    ranker.rank.return_value = reply
    return WishRankingService(savings_source, banks_source, ranker, logging.getLogger("test"))


def _step() -> NextStepResponseDTO:
    return NextStepResponseDTO.of_result(RankingResultResponseDTO(rows=()))


class WishRankingMergeTest(IsolatedAsyncioTestCase):

    async def test_LLM_순서와_근거가_응답에_반영된다(self) -> None:
        first = saving("bank:P1", eligibility=group(predicate()), base="3", maximum="3")
        second = saving("bank:P2", eligibility=group(predicate()), base="4", maximum="4")
        reply = WishRankReply(rankings=(
            RankedWishItem(product_id="bank:P1@12", reason="상황에 맞아요"),
            RankedWishItem(product_id="bank:P2@12", reason="금리가 높아요"),
        ), reply="안내 문장")
        service = _service(SavingProductsVO(products=(first, second)), reply)

        ranking: WishRanking | None = await service.rank(
            "rid", "사회초년생이에요", AnswersVO((_age_answer(),)), _step(), (),
        )

        assert ranking is not None
        assert ranking.reply == "안내 문장"
        # 금리는 P2(4%)가 높지만 LLM 이 P1 을 앞세운 순서가 유지된다
        assert [row.product_id for row in ranking.rows] == ["bank:P1", "bank:P2"]
        assert ranking.rows[0].reason == "상황에 맞아요"
        assert ranking.rows[0].rank == 1

    async def test_지어낸_후보는_버리고_빠뜨린_후보는_금리순으로_보충한다(self) -> None:
        first = saving("bank:P1", eligibility=group(predicate()), base="3", maximum="3")
        second = saving("bank:P2", eligibility=group(predicate()), base="4", maximum="4")
        reply = WishRankReply(rankings=(
            RankedWishItem(product_id="bank:없는상품@12", reason="지어낸 근거"),
            RankedWishItem(product_id="bank:P1@12", reason="상황에 맞아요"),
        ), reply="안내 문장")
        service = _service(SavingProductsVO(products=(first, second)), reply)

        ranking: WishRanking | None = await service.rank(
            "rid", "사회초년생이에요", AnswersVO((_age_answer(),)), _step(), (),
        )

        assert ranking is not None
        # 지어낸 상품은 응답에 없고, LLM 이 빠뜨린 P2 는 뒤에 보충된다
        assert [row.product_id for row in ranking.rows] == ["bank:P1", "bank:P2"]
        assert "금리 순서" in ranking.rows[1].reason

    async def test_후보가_없으면_None(self) -> None:
        reply = WishRankReply(rankings=(), reply="안내 문장")
        service = _service(SavingProductsVO(products=()), reply)

        ranking: WishRanking | None = await service.rank(
            "rid", "사회초년생이에요", AnswersVO(()), _step(), (),
        )

        assert ranking is None


def _age_answer():
    return AnswerVO("age", "25")
