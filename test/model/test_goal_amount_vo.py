from __future__ import annotations
import unittest
from app.enums.answer_value import AnswerStatus
from app.enums.saving_comparison import GoalReachStatus
from app.model.vo.goal_amount_vo import GoalAmountVO
from test.service.saving.saving_fixture import answers


class TestGoalAmountVO(unittest.TestCase):
    def test_목표금액을_답하면_금액으로_읽는다(self) -> None:
        goal = GoalAmountVO.from_answers(answers(("goal_amount", "5000000")))
        self.assertEqual(AnswerStatus.PROVIDED, goal.status)
        self.assertEqual(5000000, goal.amount)

    def test_목표금액을_건너뛰면_목표없음으로_읽는다(self) -> None:
        goal = GoalAmountVO.from_answers(answers(("goal_amount", "none")))
        self.assertEqual(AnswerStatus.UNANSWERED, goal.status)

    def test_숫자가_아닌_목표금액은_잘못된_답으로_읽는다(self) -> None:
        goal = GoalAmountVO.from_answers(answers(("goal_amount", "오백만원")))
        self.assertEqual(AnswerStatus.INVALID, goal.status)

    def test_만기액이_목표를_넘으면_달성으로_판정한다(self) -> None:
        goal = GoalAmountVO.from_answers(answers(("goal_amount", "5000000")))
        self.assertIs(GoalReachStatus.REACHED, goal.reach(5100000, 5200000))

    def test_내_금리로는_모자라도_최대금리로_닿으면_따로_알린다(self) -> None:
        goal = GoalAmountVO.from_answers(answers(("goal_amount", "5000000")))
        self.assertIs(GoalReachStatus.REACHED_AT_MAX_RATE, goal.reach(4900000, 5050000))

    def test_최대금리로도_모자라면_부족으로_판정한다(self) -> None:
        goal = GoalAmountVO.from_answers(answers(("goal_amount", "5000000")))
        self.assertIs(GoalReachStatus.SHORT, goal.reach(4000000, 4100000))

    def test_목표가_없으면_판정하지_않는다(self) -> None:
        goal = GoalAmountVO.from_answers(answers(("goal_amount", "none")))
        self.assertIs(GoalReachStatus.NO_GOAL, goal.reach(4000000, 4100000))

    def test_모자라는_금액을_알려준다(self) -> None:
        goal = GoalAmountVO.from_answers(answers(("goal_amount", "5000000")))
        self.assertEqual(1000000, goal.shortfall(4000000))

    def test_목표에_닿으면_모자라는_금액은_없다(self) -> None:
        goal = GoalAmountVO.from_answers(answers(("goal_amount", "5000000")))
        self.assertEqual(0, goal.shortfall(5000000))
