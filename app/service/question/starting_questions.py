from __future__ import annotations
from logging import Logger
from typing import TYPE_CHECKING
from infra.request_context import short_request_id
from app.dto.response.question import QuestionResponseDTO
from app.enums.answer_value import AnswerStatus

if TYPE_CHECKING:
    from app.model.vo.answers_vo import AnswersVO
    from app.model.vo.questions_vo import QuestionsVO
    from app.model.vo.saving_products_vo import SavingProductsVO


class StartingQuestions:
    """비교를 시작하기 전에 받아야 하는 세 답(기간·월납입·목표금액)을 판정한다."""

    _logger: Logger

    def __init__(self, logger: Logger) -> None:
        self._logger = logger

    def next_question_or_terms(
            self, request_id: str, answers: AnswersVO, products: SavingProductsVO, questions: QuestionsVO,
    ) -> QuestionResponseDTO | tuple[int, ...]:
        """물을 것이 남았으면 그 질문을, 다 모였으면 비교할 기간 목록을 돌려준다."""
        term_question: QuestionResponseDTO = QuestionResponseDTO.for_saving_terms(products, questions)
        selected_terms: tuple[int, ...] | None = self._selected_terms(answers, term_question, products)
        if selected_terms is None:
            self._logger.debug("기간 질문 반환 | req=%s | 질문키=%s", short_request_id(request_id), term_question.key)
            return term_question

        monthly_question: QuestionResponseDTO = QuestionResponseDTO.for_monthly_deposit(questions)
        if not answers.contains(monthly_question.key):
            return monthly_question

        goal_question: QuestionResponseDTO = QuestionResponseDTO.for_goal_amount(questions)
        if not answers.contains(goal_question.key):
            return goal_question

        return selected_terms

    @staticmethod
    def _selected_terms(
            answers: AnswersVO, term_question: QuestionResponseDTO, products: SavingProductsVO,
    ) -> tuple[int, ...] | None:
        answer: str | AnswerStatus = answers.value_of(term_question.key)

        if answer is AnswerStatus.SKIPPED:
            return products.available_saving_terms()

        if isinstance(answer, AnswerStatus):
            return None

        if not term_question.offers(answer):
            return None

        # HTTP 선택지 값은 문자열이다. 허용된 기간인지 확인한 뒤 숫자로 한 번 변환한다.
        return (int(answer),)
