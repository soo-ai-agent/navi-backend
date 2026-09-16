from __future__ import annotations
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock
from app.enums.answer_kind import AnswerKind
from app.enums.judge_kind import JudgeKind
from app.external.llm.wish_parser import WishLlmParser
from app.model.database.question import Question
from app.model.vo.wish_structure_vo import WishStructureVO


def _question(code: str, title: str) -> Question:
    return Question(code=code, title=title, answer_kind=AnswerKind.BOOLEAN, judge_kind=JudgeKind.SALARY)


class TestWishLlmParser(IsolatedAsyncioTestCase):
    async def parse(self, llm_answer: str) -> WishStructureVO:
        llm_client = AsyncMock()
        llm_client.ask_json.return_value = llm_answer
        questions = (_question("salary_transfer", "급여이체를 하시나요?"),)
        return await WishLlmParser(llm_client).parse("급여이체 되고 앱이 편한 적금이요", questions)

    async def test_아는_질문의_답과_보존_요구를_나눠_담는다(self):
        structured = await self.parse(
            '{"answers": [{"code": "salary_transfer", "value": "yes"}],'
            ' "unmapped": [{"name": "앱 사용 편의성", "text": "앱이 편한"}]}'
        )
        self.assertEqual("salary_transfer", structured.answers[0].code)
        self.assertEqual("yes", structured.answers[0].value)
        self.assertEqual("앱 사용 편의성", structured.unmapped[0].name)

    async def test_지어낸_질문_코드는_매핑하지_않고_보존한다(self):
        structured = await self.parse(
            '{"answers": [{"code": "app_usability", "value": "편해야 함"}], "unmapped": []}'
        )
        self.assertEqual((), structured.answers)
        self.assertEqual("app_usability", structured.unmapped[0].name)
        self.assertEqual("편해야 함", structured.unmapped[0].text)

    async def test_합성_키_goal_amount_의_답을_받아들인다(self):
        structured = await self.parse(
            '{"answers": [{"code": "goal_amount", "value": "2000000"}], "unmapped": []}'
        )
        self.assertEqual("goal_amount", structured.answers[0].code)
        self.assertEqual("2000000", structured.answers[0].value)

    async def test_숫자_질문의_단위_표기를_숫자로_정규화한다(self):
        llm_client = AsyncMock()
        llm_client.ask_json.return_value = (
            '{"answers": [{"code": "months", "value": "6개월"}, {"code": "monthly", "value": "300,000원"}],'
            ' "unmapped": []}'
        )
        questions = (
            Question(code="months", title="얼마 동안 넣을까요?",
                     answer_kind=AnswerKind.OPTIONS, judge_kind=JudgeKind.SAVING_TERM),
            Question(code="monthly", title="매달 얼마씩 넣을까요? (원)",
                     answer_kind=AnswerKind.NUMBER, judge_kind=JudgeKind.MONTHLY),
        )
        structured = await WishLlmParser(llm_client).parse("매달 30만원씩 6개월 넣고 싶어", questions)
        values = {answer.code: answer.value for answer in structured.answers}
        self.assertEqual("6", values["months"])
        self.assertEqual("300000", values["monthly"])

    async def test_숫자로_못_만드는_숫자_답은_버린다(self):
        llm_client = AsyncMock()
        llm_client.ask_json.return_value = '{"answers": [{"code": "months", "value": "반년쯤"}], "unmapped": []}'
        questions = (
            Question(code="months", title="얼마 동안 넣을까요?",
                     answer_kind=AnswerKind.OPTIONS, judge_kind=JudgeKind.SAVING_TERM),
        )
        structured = await WishLlmParser(llm_client).parse("반년쯤 넣고 싶어", questions)
        self.assertEqual((), structured.answers)
