from __future__ import annotations

from unittest import IsolatedAsyncioTestCase

from app.enums.saving_condition import ConditionField, ConditionOperator
from app.exception.question import SavingConditionsUnavailableError
from test.service.saving.saving_fixture import answers, bonus, group, predicate, saving, question_flow


class TestQuestionFlowLogs(IsolatedAsyncioTestCase):
    async def test_기간_질문까지_같은_요청번호로_기록한다(self):
        with self.assertLogs("test.question_flow", level="DEBUG") as logs:
            await question_flow(saving()).next_step(answers())

        messages = tuple(record.getMessage() for record in logs.records)
        request_id = messages[0].split("req=", 1)[1].split(" |", 1)[0]
        self.assertEqual(
            ("질문 처리 시작", "기간 질문 반환", "질문 처리 종료"),
            tuple(message.split(" |", 1)[0] for message in messages),
        )
        for message in messages:
            self.assertIn(f"req={request_id}", message)

    async def test_가입조건_질문을_반환한_단계를_기록한다(self):
        target = saving(eligibility=group(predicate()))
        with self.assertLogs("test.question_flow", level="DEBUG") as logs:
            await question_flow(target).next_step(answers(("months", "12")))

        output = "\n".join(logs.output)
        self.assertIn("가입조건 판정 |", output)
        self.assertIn("결과=UNKNOWN", output)
        self.assertIn("가입조건 질문 반환 |", output)
        self.assertIn("질문키=age", output)
        self.assertIn("결과=question", logs.output[-1])

    async def test_우대조건_추가질문_결정을_기록한다(self):
        target = saving(bonuses=(bonus(predicate()),))
        with self.assertLogs("test.question_flow", level="DEBUG") as logs:
            await question_flow(target).next_step(answers(("months", "12")))

        output = "\n".join(logs.output)
        self.assertIn("우대조건 판정 |", output)
        self.assertIn("금리 정렬 완료 |", output)
        self.assertIn("우대조건 질문 반환 |", output)
        self.assertIn("결과=question", logs.output[-1])

    async def test_금리계산부터_최종결과까지_기록한다(self):
        target = saving(bonuses=(bonus(predicate(ConditionField.MOBILE, ConditionOperator.EQ, (True,))),))
        with self.assertLogs("test.question_flow", level="DEBUG") as logs:
            await question_flow(target).next_step(answers(("months", "12"), ("mobile", "yes")))

        output = "\n".join(logs.output)
        self.assertIn("금리 계산 완료 |", output)
        self.assertIn("적용금리=3.7", output)
        self.assertIn("추천 결과 반환 |", output)
        self.assertIn("결과수=1", output)
        self.assertIn("결과=done", logs.output[-1])

    async def test_503도_실패_종료까지_기록한다(self):
        target = saving()
        target.condition = None
        with self.assertLogs("test.question_flow", level="DEBUG") as logs:
            with self.assertRaises(SavingConditionsUnavailableError):
                await question_flow(target).next_step(answers(("months", "12")))

        output = "\n".join(logs.output)
        self.assertIn("상품 조건 검증 종료 |", output)
        self.assertIn("status=503", output)
        self.assertIn("질문 처리 종료 |", logs.output[-1])
        self.assertIn("오류=SavingConditionsUnavailableError", logs.output[-1])
        self.assertIn("소요_ms=", logs.output[-1])
