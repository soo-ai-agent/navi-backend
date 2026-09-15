from __future__ import annotations

from dataclasses import FrozenInstanceError
from unittest import TestCase

from app.dto.request.answer import AnswerRequestDTO
from app.enums.answer_value import AnswerStatus
from app.enums.saving import MonthlyLimitStatus
from app.enums.saving_condition import ConditionField, ConditionStatus
from app.model.vo.answer_vo import AnswerVO
from app.model.vo.answers_vo import AnswersVO
from app.model.vo.condition_answer_vo import ConditionAnswerVO
from app.model.vo.condition_context_vo import ConditionContextVO
from app.model.vo.monthly_limit_vo import MonthlyLimitVO
from test.service.saving.saving_fixture import saving


class TestAnswerStates(TestCase):
    def test_답변이_없으면_미응답_상태다(self):
        self.assertIs(AnswerStatus.UNANSWERED, AnswersVO().value_of("age"))

    def test_any_입력은_건너뛰기_상태다(self):
        answers = AnswerRequestDTO.model_validate_json('{"age": "none"}').to_answers()
        self.assertIs(AnswerStatus.SKIPPED, answers.value_of("age"))
        self.assertIs(AnswerStatus.SKIPPED, answers.entries[0].status)

    def test_제공된_답변은_원래_값을_보존한다(self):
        answer = AnswerVO("age", "0")
        self.assertIs(AnswerStatus.PROVIDED, answer.status)
        self.assertEqual("0", AnswersVO((answer,)).value_of("age"))

    def test_조건이_미응답과_건너뛰기_상태를_유지한다(self):
        condition = ConditionAnswerVO(ConditionField.AGE, ConditionContextVO("bank", 12, MonthlyLimitVO.limited(500000)))
        self.assertIs(AnswerStatus.UNANSWERED, condition.number_value(AnswersVO()))
        self.assertIs(AnswerStatus.SKIPPED, condition.number_value(AnswersVO((AnswerVO("age", "none"),))))

    def test_잘못된_답은_유효하지_않은_상태다(self):
        condition = ConditionAnswerVO(ConditionField.AGE, ConditionContextVO("bank", 12, MonthlyLimitVO.limited(500000)))
        self.assertIs(AnswerStatus.INVALID, condition.number_value(AnswersVO((AnswerVO("age", "abc"),))))

    def test_아니오는_미응답과_구분한다(self):
        condition = ConditionAnswerVO(ConditionField.MOBILE, ConditionContextVO("bank", 12, MonthlyLimitVO.limited(500000)))
        self.assertIs(False, condition.boolean_value(AnswersVO((AnswerVO("mobile", "no"),))))

    def test_숫자_0은_미응답과_구분한다(self):
        condition = ConditionAnswerVO(ConditionField.AGE, ConditionContextVO("bank", 12, MonthlyLimitVO.limited(500000)))
        self.assertEqual(0, condition.number_value(AnswersVO((AnswerVO("age", "0"),))))

    def test_조건입력_VO는_엔티티_변경에_영향받지_않는다(self):
        target = saving(monthly_limit=500000)
        context = target.condition_context(target.rate_options[0])
        target.monthly_limit = 100000
        self.assertEqual(500000, context.planned_monthly_deposit(600000))

    def test_조건입력_VO는_수정할_수_없다(self):
        context = ConditionContextVO("bank", 12, MonthlyLimitVO.limited(500000))
        with self.assertRaises(FrozenInstanceError):
            setattr(context, "bank_code", "other")

    def test_한도_없음은_상태로_보존한다(self):
        context = ConditionContextVO("bank", 12, MonthlyLimitVO.from_database(None))
        self.assertEqual(MonthlyLimitStatus.UNLIMITED, context.monthly_limit.status)
        self.assertEqual(600000, context.planned_monthly_deposit(600000))

    def test_미추출_상품은_대기_상태다(self):
        target = saving()
        target.condition = None  # 추출 전에는 ORM 조건 관계가 존재하지 않는다.
        self.assertIs(ConditionStatus.PENDING, target.verified_conditions())

    def test_저장된_조건이_잘못되면_실패_상태다(self):
        target = saving()
        assert target.condition is not None
        target.condition.conditions_json = "invalid"
        self.assertIs(ConditionStatus.FAILED, target.verified_conditions())
