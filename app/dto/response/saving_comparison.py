from __future__ import annotations
from decimal import Decimal
from pydantic import BaseModel, ConfigDict
from app.enums.saving_comparison import GoalReachStatus, MaturityEstimateStatus, SavingEligibilityStatus
from app.enums.saving_condition import ConditionStatus
from app.enums.saving import InterestCalcType, ReserveType
from app.model.database.saving import Saving
from app.model.vo.saving_products_vo import SavingProductsVO
from app.model.vo.answers_vo import AnswersVO
from app.model.vo.extracted_conditions_vo import ExtractedConditionsVO
from app.model.vo.goal_amount_vo import GoalAmountVO
from app.model.vo.monthly_deposit_vo import MonthlyDepositVO
from app.model.vo.saving_option_comparison_vo import SavingOptionComparisonVO


class MaturityEstimateResponseDTO(BaseModel):
    model_config = ConfigDict(frozen=True, from_attributes=True)

    status: MaturityEstimateStatus
    monthly_deposit: int
    principal: int
    interest_before_tax: int
    maturity_before_tax: int
    maturity_at_max_rate: int
    reason: str
    """ESTIMATED가 아닌 경우 금액은 0이며 status와 reason으로 표시 불가 사유를 알린다."""


class SavingOptionComparisonResponseDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    saving_term_months: int
    reserve_type: ReserveType
    interest_calc_type: InterestCalcType
    base_rate: Decimal
    max_rate: Decimal
    applied_rate: Decimal
    eligibility_status: SavingEligibilityStatus
    eligibility_reasons: tuple[str, ...]
    estimate: MaturityEstimateResponseDTO
    goal_reach: GoalReachStatus
    goal_shortfall: int
    """목표액에서 모자라는 금액. 목표가 없거나 닿았으면 0이다."""

    @classmethod
    def from_comparison(
            cls, comparison: SavingOptionComparisonVO, goal: GoalAmountVO
    ) -> SavingOptionComparisonResponseDTO:
        return cls(
            saving_term_months=comparison.option.saving_term_months,
            reserve_type=comparison.option.reserve_type,
            interest_calc_type=comparison.option.interest_calc_type,
            base_rate=comparison.option.base_rate,
            max_rate=comparison.option.max_rate,
            applied_rate=comparison.applied_rate,
            eligibility_status=comparison.eligibility.status,
            eligibility_reasons=comparison.eligibility.reasons,
            estimate=MaturityEstimateResponseDTO.model_validate(comparison.estimate),
            goal_reach=goal.reach(comparison.estimate.maturity_before_tax, comparison.estimate.maturity_at_max_rate),
            goal_shortfall=goal.shortfall(comparison.estimate.maturity_before_tax),
        )


class SavingComparisonResponseDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    product_id: str
    options: tuple[SavingOptionComparisonResponseDTO, ...]

    @classmethod
    def from_saving(
            cls, saving: Saving, answers: AnswersVO, deposit: MonthlyDepositVO, goal: GoalAmountVO,
    ) -> SavingComparisonResponseDTO:
        extracted: ExtractedConditionsVO | ConditionStatus = saving.verified_conditions()

        options: list[SavingOptionComparisonResponseDTO] = []
        for option in saving.rate_options:
            compared: SavingOptionComparisonVO = SavingOptionComparisonVO.evaluate(
                saving, option, extracted, answers, deposit,
            )
            options.append(SavingOptionComparisonResponseDTO.from_comparison(compared, goal))

        return cls(product_id=saving.product_id, options=tuple(options))


class SavingComparisonsResponseDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    products: tuple[SavingComparisonResponseDTO, ...]

    @classmethod
    def from_savings(cls, products: SavingProductsVO, answers: AnswersVO) -> SavingComparisonsResponseDTO:
        deposit: MonthlyDepositVO = MonthlyDepositVO.from_answers(answers)
        goal: GoalAmountVO = GoalAmountVO.from_answers(answers)

        compared: list[SavingComparisonResponseDTO] = []
        for saving in products.products:
            compared.append(SavingComparisonResponseDTO.from_saving(saving, answers, deposit, goal))

        return cls(products=tuple(compared))
