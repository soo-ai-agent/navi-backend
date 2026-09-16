from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING
from infra.request_context import short_request_id
from app.dto.response.wish import WishRankedSavingResponseDTO
from app.enums.saving_condition import ConditionStatus
from app.enums.saving import BonusResult
from app.external.llm.wish_ranker import candidate_id
from app.model.vo.checked_bonus_vo import CheckedBonusVO
from app.model.vo.saving_rate import SavingRate
from app.model.vo.saving_ranking_vo import SavingRankingVO

if TYPE_CHECKING:
    from logging import Logger

    from app.dto.response.next_step import NextStepResponseDTO
    from app.external.llm.wish_ranker import RankedWishItem, WishLlmRanker, WishRankReply
    from app.model.database.saving import Saving
    from app.model.database.rate_option import RateOption
    from app.model.vo.answers_vo import AnswersVO
    from app.model.vo.banks_vo import BanksVO
    from app.model.vo.condition_context_vo import ConditionContextVO
    from app.model.vo.extracted_conditions_vo import ExtractedConditionsVO
    from app.model.vo.saving_products_vo import SavingProductsVO
    from app.model.vo.unmapped_wish_vo import UnmappedWishVO
    from app.source.banks_source import BanksSource
    from app.source.saving_products_source import SavingProductsSource

_CANDIDATE_SIZE = 10
"""LLM 에게 넘기는 후보 상품 수. 금리 상위만 추려 프롬프트 길이와 응답 시간을 묶는다"""

_UNRANKED_REASON = "상황과의 관련을 판단하지 못해 금리 순서로 두었어요."
"""LLM 이 순위에서 빠뜨린 상품에 붙이는 사유. 빠뜨려도 상품이 사라지면 안 된다"""


@dataclass(frozen=True)
class WishRanking:
    """상황 순위와 그 순위를 설명하는 답변 문장. 한 LLM 호출에서 함께 나온다."""

    rows: tuple[WishRankedSavingResponseDTO, ...]
    reply: str


class WishRankingService:
    """
    문장 대화 전용 순위. 금리·조건 판정은 규칙 엔진(Python)이 하고,
    상황에 맞는 순서와 근거 문장만 LLM 이 정한다.
    """

    _savings_source: SavingProductsSource
    _banks_source: BanksSource
    _wish_ranker: WishLlmRanker
    _logger: Logger

    def __init__(
            self,
            savings_source: SavingProductsSource,
            banks_source: BanksSource,
            wish_ranker: WishLlmRanker,
            logger: Logger,
    ) -> None:
        self._savings_source = savings_source
        self._banks_source = banks_source
        self._wish_ranker = wish_ranker
        self._logger = logger

    async def rank(
            self, request_id: str, message: str, answers: AnswersVO,
            step: NextStepResponseDTO, unmapped: tuple[UnmappedWishVO, ...],
    ) -> WishRanking | None:
        """후보가 없으면 None — 순위도 답변 문장도 만들 수 없다는 뜻이다."""
        candidates: tuple[SavingRate, ...] = await self._candidates(request_id, answers)
        if not candidates:
            return None

        banks: BanksVO = await self._banks_source.get(request_id)
        ranked: WishRankReply = await self._wish_ranker.rank(message, candidates, banks, step, unmapped)
        ordered: tuple[tuple[SavingRate, str], ...] = self._merge(request_id, candidates, ranked.rankings)

        rows: list[WishRankedSavingResponseDTO] = []
        for rank, (candidate, reason) in enumerate(ordered, start=1):
            rows.append(WishRankedSavingResponseDTO.from_rate_with_reason(
                candidate, rank, banks.name(candidate.saving.bank_code), reason,
            ))
        return WishRanking(rows=tuple(rows), reply=ranked.reply)

    async def _candidates(self, request_id: str, answers: AnswersVO) -> tuple[SavingRate, ...]:
        """가입 불가능이 확정된 상품만 빼고, 확정 금리 상위 순서로 후보를 추린다."""
        products: SavingProductsVO = await self._savings_source.get(request_id)
        terms: tuple[int, ...] = self._terms(answers, products)

        rates: list[SavingRate] = []
        for saving in products.products:
            extracted: ExtractedConditionsVO | ConditionStatus = saving.verified_conditions()
            if isinstance(extracted, ConditionStatus):
                continue

            for option in saving.rate_options:
                if option.saving_term_months not in terms:
                    continue
                context: ConditionContextVO = saving.condition_context(option)
                if extracted.eligibility.evaluate(answers, context) is BonusResult.NOT_ELIGIBLE:
                    continue
                rates.append(self._saving_rate(saving, option, extracted, answers, context))

        ranking: SavingRankingVO = SavingRankingVO.from_rates(rates)
        self._logger.info(
            "문장 순위 후보 수집 | req=%s | 후보=%d | 전달=%d",
            short_request_id(request_id), len(ranking.rates), min(len(ranking.rates), _CANDIDATE_SIZE),
        )
        return ranking.rates[:_CANDIDATE_SIZE]

    @staticmethod
    def _terms(answers: AnswersVO, products: SavingProductsVO) -> tuple[int, ...]:
        """기간 답이 있으면 그 기간만, 없으면 전 기간을 비교한다."""
        available: tuple[int, ...] = products.available_saving_terms()
        answer: object = answers.value_of("months")
        if isinstance(answer, str) and answer.isdigit() and int(answer) in available:
            return (int(answer),)
        return available

    @staticmethod
    def _saving_rate(
            saving: Saving, option: RateOption, extracted: ExtractedConditionsVO,
            answers: AnswersVO, context: ConditionContextVO,
    ) -> SavingRate:
        checked_bonuses: list[CheckedBonusVO] = []
        for bonus in extracted.bonuses:
            result: BonusResult = bonus.condition.evaluate(answers, context)
            unanswered = bonus.condition.unanswered(answers, context)
            checked_bonuses.append(CheckedBonusVO(bonus, result, unanswered))
        return SavingRate(
            saving, option, tuple(checked_bonuses), extracted.other_conditions,
            extracted.other_eligibility_conditions, extracted.other_bonus_conditions,
        )

    def _merge(
            self, request_id: str, candidates: tuple[SavingRate, ...], ranked: tuple[RankedWishItem, ...],
    ) -> tuple[tuple[SavingRate, str], ...]:
        """LLM 순서를 검증한다. 지어낸 후보는 버리고, 빠뜨린 후보는 금리 순서대로 뒤에 잇는다."""
        by_id: dict[str, SavingRate] = {candidate_id(candidate): candidate for candidate in candidates}

        ordered: list[tuple[SavingRate, str]] = []
        seen: set[str] = set()
        invented: int = 0
        for item in ranked:
            candidate: SavingRate | None = by_id.get(item.product_id)
            if candidate is None or item.product_id in seen:
                invented += 1
                continue
            seen.add(item.product_id)
            ordered.append((candidate, item.reason))

        missed: int = 0
        for candidate in candidates:
            if candidate_id(candidate) in seen:
                continue
            missed += 1
            ordered.append((candidate, _UNRANKED_REASON))

        self._logger.info(
            "문장 순위 병합 | req=%s | LLM반영=%d | 무시=%d | 보충=%d",
            short_request_id(request_id), len(seen), invented, missed,
        )
        return tuple(ordered)
