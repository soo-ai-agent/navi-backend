from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Sequence

from pydantic import BaseModel, ConfigDict

from app.enums.saving import MonthlyLimitStatus
from app.model.vo.monthly_limit_vo import MonthlyLimitVO
from app.enums.saving import BonusResult, InterestCalcType, ReserveType

if TYPE_CHECKING:
    from app.model.vo.checked_bonus_vo import CheckedBonusVO
    from app.model.vo.saving_rate import SavingRate
    from app.model.vo.other_condition_vo import OtherConditionVO


class BonusResultResponseDTO(BaseModel):
    """왜 이 금리가 나왔는지 — 우대조건 하나의 판정 근거."""

    model_config = ConfigDict(frozen=True)

    label: str
    result: BonusResult
    percentage_point: Decimal

    @classmethod
    def from_checked(cls, checked: CheckedBonusVO) -> BonusResultResponseDTO:
        return cls(
            label=checked.bonus.label, result=checked.result, percentage_point=checked.bonus.percentage_point,
        )


class OtherConditionResponseDTO(BaseModel):
    """판정하지 않은 공시 항목을 사용자 체크리스트로 표시한다."""

    model_config = ConfigDict(frozen=True)

    name: str
    value: str
    reason: str

    @classmethod
    def from_condition(cls, condition: OtherConditionVO) -> OtherConditionResponseDTO:
        return cls(name=condition.name, value=condition.value, reason=condition.reason)


def checklist(conditions: Sequence[OtherConditionVO]) -> tuple[OtherConditionResponseDTO, ...]:
    return tuple(OtherConditionResponseDTO.from_condition(condition) for condition in conditions)


class RankedSavingResponseDTO(BaseModel):
    """순위에 오른 상품 한 건."""

    model_config = ConfigDict(frozen=True)

    product_id: str
    rank: int
    bank_name: str
    product_name: str
    rate: Decimal
    """확정된 우대만 반영한 금리(%)"""

    base_rate: Decimal
    max_rate: Decimal
    reserve_type: ReserveType
    interest_calc_type: InterestCalcType
    saving_term_months: int
    monthly_limit_status: MonthlyLimitStatus
    monthly_limit: int
    """UNLIMITED일 때 값은 0이며, 한도 유무는 monthly_limit_status로 판정한다."""

    bonus_condition_text: str
    """우대조건 공시 원문. 판정 근거를 사용자가 직접 확인할 수 있게 함께 내린다"""

    bonus_results: tuple[BonusResultResponseDTO, ...]
    other_conditions: tuple[OtherConditionResponseDTO, ...]
    other_eligibility_conditions: tuple[OtherConditionResponseDTO, ...]
    other_bonus_conditions: tuple[OtherConditionResponseDTO, ...]

    @classmethod
    def from_rate(cls, rate: SavingRate, rank: int, bank_name: str) -> RankedSavingResponseDTO:
        monthly_limit: MonthlyLimitVO = MonthlyLimitVO.from_database(rate.saving.monthly_limit)
        bonus_results: list[BonusResultResponseDTO] = []
        for checked in rate.checked_bonuses:
            bonus_results.append(BonusResultResponseDTO.from_checked(checked))

        return cls(
            product_id=rate.saving.product_id,
            rank=rank,
            bank_name=bank_name,
            product_name=rate.saving.name,
            rate=rate.rate,
            base_rate=rate.option.base_rate,
            max_rate=rate.option.max_rate,
            reserve_type=rate.option.reserve_type,
            interest_calc_type=rate.option.interest_calc_type,
            saving_term_months=rate.option.saving_term_months,
            monthly_limit_status=monthly_limit.status,
            monthly_limit=monthly_limit.amount,
            bonus_condition_text=rate.saving.bonus_condition_text,
            bonus_results=tuple(bonus_results),
            other_conditions=checklist(rate.other_conditions),
            other_eligibility_conditions=checklist(rate.other_eligibility_conditions),
            other_bonus_conditions=checklist(rate.other_bonus_conditions),
        )


class RankingResultResponseDTO(BaseModel):
    """더 물을 것이 없을 때 내려가는 확정 순위."""

    model_config = ConfigDict(frozen=True)

    rows: tuple[RankedSavingResponseDTO, ...]
