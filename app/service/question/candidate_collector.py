from __future__ import annotations

from logging import Logger
from typing import TYPE_CHECKING

from infra.request_context import short_request_id
from app.dto.response.question import QuestionResponseDTO
from app.enums.saving import BonusResult
from app.enums.saving_condition import ConditionStatus
from app.model.vo.checked_bonus_vo import CheckedBonusVO
from app.model.vo.excluded_saving_vo import ExcludedSavingVO
from app.model.vo.saving_rate import SavingRate
from app.service.question.rate_candidates import RateCandidates
from app.exception.question import SavingConditionsUnavailableError

if TYPE_CHECKING:
    from app.model.database.saving import Saving
    from app.model.database.rate_option import RateOption
    from app.model.vo.answers_vo import AnswersVO
    from app.model.vo.banks_vo import BanksVO
    from app.model.vo.condition_answer_vo import ConditionAnswerVO
    from app.model.vo.condition_context_vo import ConditionContextVO
    from app.model.vo.condition_group_vo import ConditionGroupVO
    from app.model.vo.extracted_conditions_vo import ExtractedConditionsVO
    from app.model.vo.saving_products_vo import SavingProductsVO

_EXCLUDED_STATUSES: tuple[ConditionStatus, ...] = (
    ConditionStatus.PENDING, ConditionStatus.FAILED, ConditionStatus.NEEDS_REVIEW,
)

_NO_CONDITION_RECORD = "NO_RECORD"


class CandidateCollector:
    """상품을 순회하며 가입조건을 판정하고, 금리 후보와 제외 기록을 모은다."""

    _logger: Logger

    def __init__(self, logger: Logger) -> None:
        self._logger = logger

    def collect(
            self, request_id: str, answers: AnswersVO, products: SavingProductsVO,
            banks: BanksVO, selected_terms: tuple[int, ...],
    ) -> RateCandidates:
        rates: list[SavingRate] = []
        excluded: list[ExcludedSavingVO] = []
        checked_any_option: bool = False

        for saving in products.products:
            extracted: ExtractedConditionsVO | ConditionStatus = saving.verified_conditions()

            if isinstance(extracted, ConditionStatus):
                dropped: ExcludedSavingVO | None = self._excluded_saving(saving, extracted, selected_terms)
                if dropped is not None:
                    excluded.append(dropped)
                continue

            for option in self._options_in_terms(saving, selected_terms):
                checked_any_option = True
                context: ConditionContextVO = saving.condition_context(option)
                eligibility: ConditionGroupVO = extracted.eligibility
                eligibility_result: BonusResult = eligibility.evaluate(answers, context)
                self._logger.debug(
                    "가입조건 판정 | req=%s | product_id=%s | 기간=%d | 결과=%s",
                    short_request_id(request_id), saving.product_id, option.saving_term_months, eligibility_result.value,
                )

                if eligibility_result is BonusResult.NOT_ELIGIBLE:
                    continue

                if eligibility_result is BonusResult.UNKNOWN:
                    question: QuestionResponseDTO | None = self._eligibility_question(
                        request_id, answers, banks, saving, context, eligibility,
                    )
                    if question is None:
                        continue
                    # 답이 하나 늘면 모든 상품의 판정이 달라진다. 여기까지의 계산은 버리고 다음 요청에서 다시 센다.
                    return RateCandidates(rates, excluded, checked_any_option, question=question)

                rates.append(self._saving_rate(request_id, answers, saving, option, extracted, context))

        self._logger.debug(
            "상품 조건 검증 종료 | req=%s | 금리후보=%d | 조건제외=%d",
            short_request_id(request_id), len(rates), len(excluded),
        )
        return RateCandidates(rates, excluded, checked_any_option)

    @staticmethod
    def _options_in_terms(saving: Saving, selected_terms: tuple[int, ...]) -> list[RateOption]:
        options: list[RateOption] = []
        for option in saving.rate_options:
            if option.saving_term_months in selected_terms:
                options.append(option)
        return options

    def _excluded_saving(
            self, saving: Saving, status: ConditionStatus, selected_terms: tuple[int, ...],
    ) -> ExcludedSavingVO | None:
        if not self._options_in_terms(saving, selected_terms):
            return None

        stored_status: str = _NO_CONDITION_RECORD
        if saving.condition is not None:
            stored_status = saving.condition.status.value

        return ExcludedSavingVO(
            saving.product_id, stored_status, status, saving.condition_unavailable_reason(status),
        )

    def _saving_rate(
            self, request_id: str, answers: AnswersVO, saving: Saving, option: RateOption,
            extracted: ExtractedConditionsVO, context: ConditionContextVO,
    ) -> SavingRate:
        checked_bonuses: list[CheckedBonusVO] = []
        for bonus_index, bonus in enumerate(extracted.bonuses, start=1):
            result: BonusResult = bonus.condition.evaluate(answers, context)
            unanswered: tuple[ConditionAnswerVO, ...] = bonus.condition.unanswered(answers, context)
            checked_bonuses.append(CheckedBonusVO(bonus, result, unanswered))

            self._logger.debug(
                "우대조건 판정 | req=%s | product_id=%s | 기간=%d | 우대번호=%d | 결과=%s | 미응답수=%d",
                short_request_id(request_id), saving.product_id, option.saving_term_months, bonus_index,
                result.value, len(unanswered),
            )

        candidate: SavingRate = SavingRate(
            saving, option, tuple(checked_bonuses), extracted.other_conditions,
            extracted.other_eligibility_conditions, extracted.other_bonus_conditions,
        )
        self._logger.debug(
            "금리 계산 완료 | req=%s | product_id=%s | 기간=%d | 적용금리=%s",
            short_request_id(request_id), saving.product_id, option.saving_term_months, candidate.rate,
        )
        return candidate

    def _eligibility_question(
            self, request_id: str, answers: AnswersVO, banks: BanksVO, saving: Saving,
            context: ConditionContextVO, eligibility: ConditionGroupVO,
    ) -> QuestionResponseDTO | None:
        unanswered: tuple[ConditionAnswerVO, ...] = eligibility.unanswered(answers, context)

        if not unanswered:
            self._logger.debug(
                "가입조건 미확정 제외 | req=%s | product_id=%s | 추가질문수=0", short_request_id(request_id), saving.product_id
            )
            return None

        bank_name: str = banks.name(saving.bank_code)
        question: QuestionResponseDTO = QuestionResponseDTO.from_condition(unanswered[0], bank_name, banks)
        self._logger.debug("가입조건 질문 반환 | req=%s | 질문키=%s", short_request_id(request_id), question.key)
        return question

    def unavailable_error(
            self, request_id: str, products: SavingProductsVO, selected_terms: tuple[int, ...],
            excluded: list[ExcludedSavingVO],
    ) -> SavingConditionsUnavailableError:
        status_counts: str = ", ".join(
            f"{condition_status.value}={sum(1 for saving in excluded if saving.status is condition_status)}"
            for condition_status in _EXCLUDED_STATUSES
        )
        self._logger.warning(
            "질문 비교 불가 | req=%s | status=503 | 선택기간=%s | 조회상품=%d | 조건제외상품=%d | 제외내역=%s",
            short_request_id(request_id), selected_terms, len(products.products), len(excluded), status_counts,
        )

        distinct_reasons: set[str] = set()
        for saving in excluded:
            self._logger.debug(
                "질문 비교 제외 상품 | req=%s | product_id=%s | 저장상태=%s | 판정상태=%s | 사유=%s",
                short_request_id(request_id), saving.product_id, saving.stored_status, saving.status.value, saving.reason,
            )
            distinct_reasons.add(saving.reason)

        return SavingConditionsUnavailableError(
            "상품 조건을 확인할 수 없어 비교를 진행할 수 없습니다. " + " ".join(sorted(distinct_reasons))
        )
