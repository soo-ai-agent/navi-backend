from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence
from app.enums.next_step import NextStepStatus
from app.model.vo.condition_answer_vo import ConditionAnswerVO
from app.model.vo.saving_rate import SavingRate


@dataclass(frozen=True)
class SavingRankingVO:

    rates: tuple[SavingRate, ...]

    @classmethod
    def from_rates(cls, rates: Sequence[SavingRate]) -> SavingRankingVO:
        best_rates: dict[tuple[str, int], SavingRate] = {}
        for candidate in rates:
            saving_and_term: tuple[str, int] = (
                candidate.saving.product_id, candidate.option.saving_term_months,
            )

            current: SavingRate | None = best_rates.get(saving_and_term)
            if current is not None and current.rate >= candidate.rate:
                continue

            best_rates[saving_and_term] = candidate

        highest_first: list[SavingRate] = sorted(
            best_rates.values(), key=lambda entry: entry.rate, reverse=True,
        )
        return cls(tuple(highest_first))

    def next_answer(self) -> ConditionAnswerVO | NextStepStatus:
        if not self.rates:
            return NextStepStatus.DONE

        leader_rate: Decimal = self.rates[0].rate
        best_gain: Decimal = Decimal(0)
        next_answer: ConditionAnswerVO | NextStepStatus = NextStepStatus.DONE

        for candidate in self.rates:
            possible_gain: Decimal = candidate.possible_rate - leader_rate
            if possible_gain <= best_gain:
                continue

            unanswered: ConditionAnswerVO | None = candidate.first_unanswered()
            if unanswered is None:
                continue

            best_gain = possible_gain
            next_answer = unanswered

        return next_answer
