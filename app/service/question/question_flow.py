from __future__ import annotations

from logging import Logger
from time import perf_counter
from typing import TYPE_CHECKING

from infra.request_context import current_request_id, short_request_id
from app.dto.response.next_step import NextStepResponseDTO
from app.dto.response.question import QuestionResponseDTO
from app.service.question.candidate_collector import CandidateCollector
from app.service.question.ranking_step import RankingStep
from app.service.question.starting_questions import StartingQuestions

if TYPE_CHECKING:
    from app.model.vo.answers_vo import AnswersVO
    from app.model.vo.banks_vo import BanksVO
    from app.model.vo.questions_vo import QuestionsVO
    from app.model.vo.saving_products_vo import SavingProductsVO
    from app.service.question.rate_candidates import RateCandidates
    from app.source.banks_source import BanksSource
    from app.source.saving_products_source import SavingProductsSource
    from app.source.questions_source import QuestionsSource


class QuestionFlowService:
    _savings_source: SavingProductsSource
    _bank_service: BanksSource
    _questions_service: QuestionsSource
    _starting_questions: StartingQuestions
    _candidate_collector: CandidateCollector
    _ranking_step: RankingStep
    _logger: Logger

    def __init__(
            self, savings_source: SavingProductsSource, bank_service: BanksSource,
            questions_service: QuestionsSource, logger: Logger,
    ) -> None:
        self._savings_source = savings_source
        self._bank_service = bank_service
        self._questions_service = questions_service
        # 세 협력자는 로거 말고는 상태가 없다. 컨테이너 등록 대신 여기서 만든다.
        self._starting_questions = StartingQuestions(logger)
        self._candidate_collector = CandidateCollector(logger)
        self._ranking_step = RankingStep(logger)
        self._logger = logger

    async def next_step(self, answers: AnswersVO) -> NextStepResponseDTO:
        request_id: str = current_request_id()
        started_at: float = perf_counter()
        self._logger.info("질문 처리 시작 | req=%s | 답변수=%d", short_request_id(request_id), len(answers.entries))

        try:
            step: NextStepResponseDTO = await self._decide(request_id, answers)
        except Exception as error:
            self._logger.info(
                "질문 처리 종료 | req=%s | 결과=실패 | 오류=%s | 소요_ms=%.1f",
                short_request_id(request_id), type(error).__name__, (perf_counter() - started_at) * 1000,
            )
            raise

        self._logger.info(
            "질문 처리 종료 | req=%s | 결과=%s | 소요_ms=%.1f",
            short_request_id(request_id), step.status.value, (perf_counter() - started_at) * 1000,
        )
        return step

    async def _decide(self, request_id: str, answers: AnswersVO) -> NextStepResponseDTO:
        products: SavingProductsVO = await self._savings_source.get(request_id)
        questions: QuestionsVO = await self._questions_service.get(request_id)

        opening: QuestionResponseDTO | tuple[int, ...] = self._starting_questions.next_question_or_terms(
            request_id, answers, products, questions,
        )
        if isinstance(opening, QuestionResponseDTO):
            return NextStepResponseDTO.of_question(opening)
        selected_terms: tuple[int, ...] = opening

        banks: BanksVO = await self._bank_service.get(request_id)
        candidates: RateCandidates = self._candidate_collector.collect(
            request_id, answers, products, banks, selected_terms,
        )

        if candidates.question is not None:
            return NextStepResponseDTO.of_question(candidates.question)

        if not candidates.checked_any_option:
            raise self._candidate_collector.unavailable_error(request_id, products, selected_terms, candidates.excluded)

        return self._ranking_step.ranked_step(request_id, banks, candidates.rates)
