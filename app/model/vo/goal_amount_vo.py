from __future__ import annotations
from dataclasses import dataclass
from app.constants.question_text import GOAL_AMOUNT_KEY
from app.enums.answer_value import AnswerStatus
from app.enums.saving_comparison import GoalReachStatus
from app.model.vo.answered_amount_vo import AnsweredAmountVO
from app.model.vo.answers_vo import AnswersVO


@dataclass(frozen=True)
class GoalAmountVO(AnsweredAmountVO):
    @classmethod
    def from_answers(cls, answers: AnswersVO) -> GoalAmountVO:
        return cls.of(answers, GOAL_AMOUNT_KEY)

    def reach(self, maturity_before_tax: int, maturity_at_max_rate: int) -> GoalReachStatus:
        if self.status is not AnswerStatus.PROVIDED:
            return GoalReachStatus.NO_GOAL
        if maturity_before_tax <= 0:
            return GoalReachStatus.NO_GOAL
        if maturity_before_tax >= self.amount:
            return GoalReachStatus.REACHED
        if maturity_at_max_rate >= self.amount:
            return GoalReachStatus.REACHED_AT_MAX_RATE
        return GoalReachStatus.SHORT

    def shortfall(self, maturity_before_tax: int) -> int:
        if self.status is not AnswerStatus.PROVIDED or maturity_before_tax >= self.amount:
            return 0
        return self.amount - maturity_before_tax
