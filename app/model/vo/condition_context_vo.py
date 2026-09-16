from __future__ import annotations
from dataclasses import dataclass
from app.model.vo.monthly_limit_vo import MonthlyLimitVO


@dataclass(frozen=True)
class ConditionContextVO:
    bank_code: str
    saving_term_months: int
    monthly_limit: MonthlyLimitVO

    def planned_monthly_deposit(self, budget: int) -> int:
        return self.monthly_limit.applies_to(budget)
