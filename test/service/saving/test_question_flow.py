from __future__ import annotations
from decimal import Decimal
from unittest import IsolatedAsyncioTestCase
from app.enums.saving_condition import ConditionField, ConditionOperator
from test.service.saving.saving_fixture import answers, bonus, group, predicate, saving, question_flow, raw_answers


class TestQuestionFlow(IsolatedAsyncioTestCase):
    async def test_기간을_고르면_월납입액을_묻는다(self) -> None:
        flow = question_flow(saving())

        step = await flow.next_step(raw_answers(("months", "12")))

        assert step.question is not None
        self.assertEqual("monthly", step.question.key)

    async def test_월납입액은_선택지와_직접_입력_모두_숫자로_판정한다(self) -> None:
        for amount, expected_count in (("100000", 0), ("300000", 0), ("500000", 0), ("1000000", 1),
                                       ("749999", 0), ("750000", 1)):
            with self.subTest(amount=amount):
                target = saving(
                    eligibility=group(predicate(ConditionField.MONTHLY_DEPOSIT, values=(750000,))),
                    monthly_limit=2000000,
                )
                flow = question_flow(target)

                step = await flow.next_step(answers(("months", "12"), ("monthly", amount)))

                assert step.result is not None
                self.assertEqual(expected_count, len(step.result.rows))

    async def test_답이_없으면_기간부터_묻는다(self):
        flow = question_flow(saving())

        step = await flow.next_step(answers())

        assert step.question is not None
        self.assertEqual("months", step.question.key)

    async def test_응답의_질문키로_답을_누적하면_우대금리를_계산한다(self):
        target = saving(
            eligibility=group(predicate()),
            bonuses=(bonus(predicate(ConditionField.MOBILE, ConditionOperator.EQ, (True,))),),
        )
        flow = question_flow(target)

        first = await flow.next_step(answers())
        assert first.question is not None
        term_answer = (first.question.key, "12")
        second = await flow.next_step(answers(term_answer))
        assert second.question is not None
        age_answer = (second.question.key, "19")
        third = await flow.next_step(answers(term_answer, age_answer))
        assert third.question is not None
        mobile_answer = (third.question.key, "yes")
        result = await flow.next_step(answers(term_answer, age_answer, mobile_answer))

        assert result.result is not None
        self.assertEqual(Decimal("3.7"), result.result.rows[0].rate)

    async def test_이전_답을_빼고_보내면_서버가_기억하지_않는다(self):
        flow = question_flow(saving(eligibility=group(predicate())))
        await flow.next_step(answers(("months", "12")))

        step = await flow.next_step(answers(("age", "19")))

        assert step.question is not None
        self.assertEqual("months", step.question.key)

    async def test_수정한_답_전체를_보내면_가입조건을_다시_판정한다(self):
        flow = question_flow(saving(eligibility=group(predicate())))
        await flow.next_step(answers(("months", "12"), ("age", "19")))

        step = await flow.next_step(answers(("months", "12"), ("age", "18")))

        assert step.result is not None
        self.assertEqual((), step.result.rows)

    async def test_가입_나이의_경계값으로_추천_여부를_판정한다(self):
        for age, expected_count in (("18", 0), ("19", 1), ("20", 1)):
            with self.subTest(age=age):
                flow = question_flow(saving(eligibility=group(predicate())))

                step = await flow.next_step(answers(("months", "12"), ("age", age)))

                assert step.result is not None
                self.assertEqual(expected_count, len(step.result.rows))
