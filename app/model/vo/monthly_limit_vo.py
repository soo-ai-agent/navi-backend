from __future__ import annotations
from dataclasses import dataclass
from app.enums.saving import MonthlyLimitStatus


@dataclass(frozen=True)
class MonthlyLimitVO:
    status: MonthlyLimitStatus
    amount: int = 0

    def __post_init__(self) -> None:
        if self.amount < 0:
            raise ValueError("월 납입 한도는 음수일 수 없습니다")
        if self.status is MonthlyLimitStatus.UNLIMITED and self.amount != 0:
            raise ValueError("한도 없음 상태의 금액은 0이어야 합니다")

    @classmethod
    def limited(cls, amount: int) -> MonthlyLimitVO:
        return cls(MonthlyLimitStatus.LIMITED, amount)

    @classmethod
    def unlimited(cls) -> MonthlyLimitVO:
        return cls(MonthlyLimitStatus.UNLIMITED)

    @classmethod
    def from_database(cls, value: int | None) -> MonthlyLimitVO:
        # SQL NULL은 외부 공시·기존 DB가 "한도 없음"을 표시하는 경계값이다. 내부에는 상태로만 전달한다.
        if value is None:
            return cls.unlimited()
        return cls.limited(value)

    def applies_to(self, budget: int) -> int:
        if budget < 0:
            raise ValueError("월 납입액은 음수일 수 없습니다")
        if self.status is MonthlyLimitStatus.UNLIMITED:
            return budget
        return min(budget, self.amount)
