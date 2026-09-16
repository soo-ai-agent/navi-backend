from __future__ import annotations
from logging import Logger
from typing import TYPE_CHECKING
from infra.request_context import short_request_id
from app.dto.response.next_step import NextStepResponseDTO
from app.dto.response.question import QuestionResponseDTO
from app.dto.response.ranking import RankedSavingResponseDTO, RankingResultResponseDTO
from app.enums.next_step import NextStepStatus
from app.model.vo.condition_answer_vo import ConditionAnswerVO
from app.model.vo.saving_ranking_vo import SavingRankingVO

if TYPE_CHECKING:
    from app.model.vo.banks_vo import BanksVO
    from app.model.vo.saving_rate import SavingRate

_RESULT_SIZE = 10


class RankingStep:
    """금리 후보를 정렬해, 우대 추가질문을 던질지 확정 순위를 돌려줄지 결정한다."""

    _logger: Logger

    def __init__(self, logger: Logger) -> None:
        self._logger = logger

    def ranked_step(self, request_id: str, banks: BanksVO, rates: list[SavingRate]) -> NextStepResponseDTO:
        ranking: SavingRankingVO = SavingRankingVO.from_rates(rates)
        self._logger.info(
            "금리 정렬 완료 | req=%s | 후보옵션수=%d | 상품기간수=%d",
            short_request_id(request_id), len(rates), len(ranking.rates),
        )

        next_answer: ConditionAnswerVO | NextStepStatus = ranking.next_answer()
        if isinstance(next_answer, ConditionAnswerVO):
            bank_name: str = banks.name(next_answer.context.bank_code)
            question: QuestionResponseDTO = QuestionResponseDTO.from_condition(next_answer, bank_name, banks)
            self._logger.debug("우대조건 질문 반환 | req=%s | 질문키=%s", short_request_id(request_id), question.key)
            return NextStepResponseDTO.of_question(question)

        rows: list[RankedSavingResponseDTO] = []
        for rank, rate in enumerate(ranking.rates[:_RESULT_SIZE], start=1):
            bank_name = banks.name(rate.saving.bank_code)
            rows.append(RankedSavingResponseDTO.from_rate(rate, rank, bank_name))

        self._logger.info("추천 결과 반환 | req=%s | 결과수=%d", short_request_id(request_id), len(rows))
        return NextStepResponseDTO.of_result(RankingResultResponseDTO(rows=tuple(rows)))
