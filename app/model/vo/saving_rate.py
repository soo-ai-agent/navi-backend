from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING
from app.enums.saving import BonusResult

if TYPE_CHECKING:
    from app.model.database.rate_option import RateOption
    from app.model.database.saving import Saving
    from app.model.vo.checked_bonus_vo import CheckedBonusVO
    from app.model.vo.condition_answer_vo import ConditionAnswerVO
    from app.model.vo.other_condition_vo import OtherConditionVO


@dataclass(frozen=True)
class SavingRate:
    """
    이 상품 이 기간의 금리가 지금 얼마인가, 그리고 왜 그런가.

    확정된 우대만 더한 값이라 답이 쌓일 때마다 달라진다. 정렬은 ProductRankingVO가 한다.
    """

    saving: Saving
    option: RateOption
    checked_bonuses: tuple[CheckedBonusVO, ...]
    # 판정하지 않고 상품 결과에 체크리스트로만 보여줄 항목이다.
    other_conditions: tuple[OtherConditionVO, ...] = ()
    other_eligibility_conditions: tuple[OtherConditionVO, ...] = ()
    other_bonus_conditions: tuple[OtherConditionVO, ...] = ()

    @property
    def rate(self) -> Decimal:
        """확정된 우대만 더한 금리. 공시 상한을 넘지 않는다."""
        points: Decimal = Decimal(0)
        for checked in self.checked_bonuses:
            if checked.result is BonusResult.ELIGIBLE:
                points += checked.bonus.percentage_point
        return self.option.rate_with(points)

    @property
    def unknown_bonuses(self) -> tuple[CheckedBonusVO, ...]:
        unknown: list[CheckedBonusVO] = []
        for checked in self.checked_bonuses:
            if checked.result is BonusResult.UNKNOWN:
                unknown.append(checked)
        return tuple(unknown)

    def first_unanswered(self) -> ConditionAnswerVO | None:
        """
        이 상품의 금리를 올리려면 먼저 받아야 하는 답.

        판단하지 못한 우대가 있어도 물을 것이 없을 수 있어 None 으로 알린다.
        """
        for checked in self.unknown_bonuses:
            if checked.unanswered:
                return checked.unanswered[0]
        return None

    @property
    def possible_rate(self) -> Decimal:
        possible: Decimal = self.rate
        for checked in self.unknown_bonuses:
            possible += checked.bonus.percentage_point
        return min(possible, self.option.max_rate)
