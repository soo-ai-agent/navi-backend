from __future__ import annotations
from dataclasses import dataclass
from app.enums.answer_value import AnswerStatus
from app.model.vo.answered_amount_vo import AnsweredAmountVO
from app.model.vo.answers_vo import AnswersVO
from app.model.vo.monthly_limit_vo import MonthlyLimitVO

MONTHLY_DEPOSIT_KEY = "monthly"


@dataclass(frozen=True)
class MonthlyDepositVO(AnsweredAmountVO):

    @classmethod
    def from_answers(cls, answers: AnswersVO) -> MonthlyDepositVO:
        return cls.of(answers, MONTHLY_DEPOSIT_KEY)

    def exceeds(self, limit: MonthlyLimitVO) -> bool:
        return self.status is AnswerStatus.PROVIDED and self.amount > limit.applies_to(self.amount)
