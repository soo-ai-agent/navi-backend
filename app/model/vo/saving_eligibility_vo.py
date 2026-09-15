from __future__ import annotations

from dataclasses import dataclass

from app.enums.answer_value import AnswerStatus
from app.enums.saving import MonthlyLimitStatus
from app.enums.saving_comparison import SavingEligibilityStatus
from app.enums.saving_condition import ConditionStatus
from app.enums.saving import BonusResult
from app.model.database.saving import Saving
from app.model.vo.answers_vo import AnswersVO
from app.model.vo.condition_context_vo import ConditionContextVO
from app.model.vo.extracted_conditions_vo import ExtractedConditionsVO
from app.model.vo.maturity_estimate_vo import MaturityEstimateVO
from app.model.vo.monthly_deposit_vo import MonthlyDepositVO


@dataclass(frozen=True)
class SavingEligibilityVO:
    status: SavingEligibilityStatus
    reasons: tuple[str, ...]

    @classmethod
    def evaluate(
            cls, saving: Saving, extracted: ExtractedConditionsVO | ConditionStatus,
            answers: AnswersVO, context: ConditionContextVO, deposit: MonthlyDepositVO,
    ) -> SavingEligibilityVO:
        # 한도를 넘겨 답했어도 한도까지 넣으면 가입할 수 있다 — 가입 불가가 아니라 금액만 줄여 계산한다.
        has_special_terms: bool = MaturityEstimateVO.has_special_payment_terms(saving)
        if isinstance(extracted, ConditionStatus):
            return cls(SavingEligibilityStatus.NEEDS_CONFIRMATION, (
                saving.condition_unavailable_reason(extracted),
                "가입조건과 우대조건을 확인하기 전이므로 기본금리만 반영했습니다.",
            ))

        eligibility: BonusResult = extracted.eligibility.evaluate(answers, context)
        if eligibility is BonusResult.NOT_ELIGIBLE:
            return cls(SavingEligibilityStatus.NOT_ELIGIBLE, ("입력한 답변이 상품의 가입 자격을 충족하지 않습니다.",))

        reasons: list[str] = []
        if has_special_terms:
            # 일·주 단위 납입 상품은 월 기준으로 단정할 수 없어 확인 상태로 둔다.
            reasons.append("납입 조건을 확인해야 합니다.")
        if eligibility is BonusResult.UNKNOWN:
            reasons.append("가입 자격에 필요한 답변이 없거나 올바르지 않아 확인이 필요합니다.")
        for condition in extracted.other_eligibility_conditions:
            reasons.append(f"{condition.name}: {condition.value}")
        if deposit.status is AnswerStatus.INVALID:
            reasons.append("월 납입액을 올바르게 입력해야 납입조건을 확인할 수 있습니다.")
        if deposit.status is AnswerStatus.UNANSWERED and context.monthly_limit.status is MonthlyLimitStatus.LIMITED:
            reasons.append("월 납입액을 입력해야 상품의 납입 한도를 확인할 수 있습니다.")
        if reasons:
            return cls(SavingEligibilityStatus.NEEDS_CONFIRMATION, tuple(reasons))
        return cls(SavingEligibilityStatus.ELIGIBLE, ("입력한 답변으로 확인한 가입 자격을 충족합니다.",))
