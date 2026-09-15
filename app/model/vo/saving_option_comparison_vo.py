from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.enums.saving_condition import ConditionStatus
from app.enums.saving import BonusResult
from app.model.database.saving import Saving
from app.model.database.rate_option import RateOption
from app.model.vo.answers_vo import AnswersVO
from app.model.vo.checked_bonus_vo import CheckedBonusVO
from app.model.vo.condition_context_vo import ConditionContextVO
from app.model.vo.extracted_conditions_vo import ExtractedConditionsVO
from app.model.vo.maturity_estimate_vo import MaturityEstimateVO
from app.model.vo.monthly_deposit_vo import MonthlyDepositVO
from app.model.vo.saving_eligibility_vo import SavingEligibilityVO
from app.model.vo.saving_rate import SavingRate


@dataclass(frozen=True)
class SavingOptionComparisonVO:
    option: RateOption
    applied_rate: Decimal
    eligibility: SavingEligibilityVO
    estimate: MaturityEstimateVO

    @classmethod
    def evaluate(
            cls, saving: Saving, option: RateOption, extracted: ExtractedConditionsVO | ConditionStatus,
            answers: AnswersVO, deposit: MonthlyDepositVO,
    ) -> SavingOptionComparisonVO:
        context: ConditionContextVO = saving.condition_context(option)
        condition_answers: AnswersVO = answers
        if MaturityEstimateVO.has_special_payment_terms(saving):
            # 일·주 단위 상품에 월 예산을 대입하면 금액 조건과 우대금리를 잘못 확정할 수 있다.
            condition_answers = AnswersVO(tuple(answer for answer in answers.entries if answer.key not in ("monthly", "principal")))
        eligibility: SavingEligibilityVO = SavingEligibilityVO.evaluate(saving, extracted, condition_answers, context, deposit)
        checked_bonuses: list[CheckedBonusVO] = []
        if not isinstance(extracted, ConditionStatus):
            for bonus in extracted.bonuses:
                result: BonusResult = bonus.condition.evaluate(condition_answers, context)
                checked_bonuses.append(CheckedBonusVO(bonus, result))
        rate: SavingRate = SavingRate(saving, option, tuple(checked_bonuses))
        applied_rate: Decimal = rate.rate
        estimate: MaturityEstimateVO = MaturityEstimateVO.from_saving(
            saving, option, deposit, applied_rate, eligibility.status,
        )
        return cls(option, applied_rate, eligibility, estimate)
