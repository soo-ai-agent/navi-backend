"""관리자 LLM 단건 시험 — 프롬프트·원시응답·파싱 결과가 응답에 담기는지 검증한다 (LLM 은 mock)."""

from __future__ import annotations
import logging
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock
from app.dto.response.admin_llm import LlmTestResponseDTO
from app.exception.saving import SavingNotFoundError
from app.external.llm import LlmClient
from app.model.vo.questions_vo import QuestionsVO
from app.model.vo.saving_products_vo import SavingProductsVO
from app.service.admin.llm_test import AdminLlmTestService
from app.source.questions_source import QuestionsSource
from app.source.saving_products_source import SavingProductsSource
from test.service.saving.saving_fixture import group, predicate, saving


def _service(llm_answer: str, products: SavingProductsVO = SavingProductsVO(products=())) -> AdminLlmTestService:
    llm_client = AsyncMock(spec=LlmClient)
    llm_client.ask_json.return_value = llm_answer
    savings_source = AsyncMock(spec=SavingProductsSource)
    savings_source.get.return_value = products
    questions_source = AsyncMock(spec=QuestionsSource)
    questions_source.get.return_value = QuestionsVO(())
    return AdminLlmTestService(
        llm_client, savings_source, AsyncMock(), questions_source, AsyncMock(),
        logging.getLogger("test.admin_llm"),
    )


class AdminLlmTestServiceTest(IsolatedAsyncioTestCase):

    async def test_문장_구조화_시험이_프롬프트와_원문과_결과를_담는다(self) -> None:
        raw: str = '{"answers": [{"code": "goal_amount", "value": "2000000"}], "unmapped": []}'
        service = _service(raw)

        result: LlmTestResponseDTO = await service.test_wish_parse("200만원 모으고 싶어요")

        self.assertIn("질문 목록", result.prompt)
        self.assertEqual("200만원 모으고 싶어요", result.user_content)
        self.assertEqual(raw, result.raw_response)
        self.assertIsNone(result.parse_error)
        self.assertEqual("goal_amount", result.parsed.answers[0].code)

    async def test_문장_구조화_검증_실패면_원문은_남고_오류가_담긴다(self) -> None:
        service = _service("형식이 아닌 응답")

        result: LlmTestResponseDTO = await service.test_wish_parse("아무 문장")

        self.assertEqual("형식이 아닌 응답", result.raw_response)
        self.assertIsNone(result.parsed)
        self.assertIsNotNone(result.parse_error)

    async def test_공시_구조화는_없는_상품이면_예외를_던진다(self) -> None:
        service = _service("{}")

        with self.assertRaises(SavingNotFoundError):
            await service.test_condition_parse("bank:없는상품")

    async def test_공시_구조화_시험이_상품_원문으로_실행된다(self) -> None:
        raw: str = '{"eligibility": {"match": "all", "conditions": []}, "bonuses": [], "unresolved": []}'
        products = SavingProductsVO(products=(saving("bank:P1", eligibility=group(predicate())),))
        service = _service(raw, products)

        result: LlmTestResponseDTO = await service.test_condition_parse("bank:P1")

        self.assertIn("bank:P1", result.user_content)
        self.assertEqual(raw, result.raw_response)

    async def test_안내문_시험이_LLM_답변_문장을_담는다(self) -> None:
        service = _service('{"reply": "안내 문장입니다"}')

        result: LlmTestResponseDTO = await service.test_wish_reply({})

        self.assertEqual("안내 문장입니다", result.parsed)
        self.assertIsNone(result.parse_error)
