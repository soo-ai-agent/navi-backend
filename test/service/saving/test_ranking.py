from __future__ import annotations

from decimal import Decimal
from unittest import IsolatedAsyncioTestCase

from pydantic import ValidationError

from app.dto.request.answer import AnswerRequestDTO
from app.enums.answer_value import AnswerStatus
from app.enums.next_step import NextStepStatus
from app.enums.saving_condition import ConditionField as F, ConditionOperator as O, ConditionMatch as M, ConditionStatus
from app.enums.saving import BonusResult
from app.exception.question import SavingConditionsUnavailableError
from test.service.saving.saving_fixture import answers, bonus, group, predicate, saving, question_flow


class TestRecommendation(IsolatedAsyncioTestCase):
    async def test_필수조건부터_질문한다(self):
        target = saving(eligibility=group(predicate()), bonuses=(bonus(predicate(F.MOBILE, O.EQ, (True,))),))
        step = (await question_flow(target).next_step(answers(("months", "12"))))
        assert step.question is not None
        self.assertEqual("age", step.question.key)

    async def test_필수조건_불충족은_추천에서_제외한다(self):
        step = (await question_flow(saving(eligibility=group(predicate()))).next_step(answers(("months", "12"), ("age", "18"))))
        assert step.result is not None
        self.assertEqual((), step.result.rows)

    async def test_건너뛴_필수조건을_충족으로_간주하지_않는다(self):
        step = (await question_flow(saving(eligibility=group(predicate()))).next_step(answers(("months", "12"), ("age", "none"))))
        assert step.result is not None
        self.assertEqual((), step.result.rows)

    async def test_잘못된_필수조건_답으로_서버오류를_내지_않는다(self):
        step = (await question_flow(saving(eligibility=group(predicate()))).next_step(answers(("months", "12"), ("age", "abc"))))
        assert step.result is not None
        self.assertEqual((), step.result.rows)

    async def test_추출되지_않거나_검토필요한_상품을_제외한다(self):
        for status in (ConditionStatus.PENDING, ConditionStatus.NEEDS_REVIEW, ConditionStatus.FAILED):
            with self.subTest(status=status):
                target = saving()
                assert target.condition is not None
                target.condition.status = status
                with self.assertRaises(SavingConditionsUnavailableError):
                    await question_flow(target).next_step(answers(("months", "12")))

    async def test_조건_행이_없는_상품을_제외한다(self):
        target = saving()
        target.condition = None
        with self.assertRaises(SavingConditionsUnavailableError):
            await question_flow(target).next_step(answers(("months", "12")))

    async def test_원문이_바뀐_조건을_추천에_쓰지_않는다(self):
        target = saving()
        target.join_member = "변경된 조건"
        with self.assertRaises(SavingConditionsUnavailableError):
            await question_flow(target).next_step(answers(("months", "12")))

    async def test_구버전_조건을_추천에_쓰지_않는다(self):
        target = saving()
        assert target.condition is not None
        target.condition.schema_version = "old"
        with self.assertRaises(SavingConditionsUnavailableError):
            await question_flow(target).next_step(answers(("months", "12")))

    async def test_복합_우대는_충족시_한번만_더한다(self):
        target = saving(bonuses=(bonus(predicate(), predicate(F.MOBILE, O.EQ, (True,)), match=M.ANY),))
        step = (await question_flow(target).next_step(answers(("months", "12"), ("age", "20"), ("mobile", "yes"))))
        assert step.result is not None
        self.assertEqual(Decimal("3.7"), step.result.rows[0].rate)
        self.assertEqual(1, len(step.result.rows[0].bonus_results))

    async def test_일위를_바꿀_수_있는_우대를_묻는다(self):
        leader = saving("bank:L", base="3.5")
        challenger = saving("bank:C", bonuses=(bonus(predicate()),))
        step = (await question_flow(leader, challenger).next_step(answers(("months", "12"))))
        assert step.question is not None
        self.assertEqual("age", step.question.key)

    async def test_일위를_바꿀_수_없는_우대는_묻지_않는다(self):
        leader = saving("bank:L", base="4")
        challenger = saving("bank:C", bonuses=(bonus(predicate()),))
        step = (await question_flow(leader, challenger).next_step(answers(("months", "12"))))
        self.assertIs(NextStepStatus.DONE, step.status)
        assert step.result is not None
        self.assertEqual("bank:L", step.result.rows[0].product_id)
        self.assertIs(BonusResult.UNKNOWN, step.result.rows[1].bonus_results[0].result)

    async def test_선택한_기간의_옵션만_추천한다(self):
        step = (await question_flow(saving(term=24)).next_step(answers(("months", "24"))))
        assert step.result is not None
        self.assertEqual(24, step.result.rows[0].saving_term_months)

    async def test_잘못된_기간은_다시_질문한다(self):
        step = await question_flow(saving()).next_step(answers(("months", "oops")))
        assert step.question is not None
        self.assertEqual("months", step.question.key)

    async def test_건너뛴_우대는_더하지_않고_반복질문하지_않는다(self):
        step = (await question_flow(saving(bonuses=(bonus(predicate()),))).next_step(answers(("months", "12"), ("age", "none"))))
        assert step.result is not None
        self.assertEqual(Decimal("3"), step.result.rows[0].rate)

    async def test_요청_답은_문자열만_받는다(self):
        for value in ('{"age": 20}', '{"age": true}', '{"age": []}', '{"age": null}'):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                AnswerRequestDTO.model_validate_json(value)

    async def test_건너뛴_답을_불변_답_목록으로_전달한다(self):
        submitted = AnswerRequestDTO.model_validate_json('{"age": "none", "months": "12"}').to_answers()
        self.assertIs(AnswerStatus.SKIPPED, submitted.value_of("age"))
        self.assertEqual("12", submitted.value_of("months"))

    async def test_root도_평문_JSON의_질문키로_보존한다(self):
        payload = '{"root":"12"}'

        request = AnswerRequestDTO.model_validate_json(payload)

        self.assertEqual(payload, request.model_dump_json())
        self.assertEqual("12", request.to_answers().value_of("root"))
