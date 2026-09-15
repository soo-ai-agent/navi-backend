from __future__ import annotations

from unittest import IsolatedAsyncioTestCase, TestCase

import httpx
from pydantic import ValidationError

from app.dto.request.answer import AnswerRequestDTO
from app.enums.saving_condition import ConditionStatus
from app.external.llm.exception import ConditionExtractionError, LlmApiError
from app.exception.condition import ConditionVerificationError
from app.model.vo.condition_predicate_vo import ConditionPredicateVO
from app.model.vo.extracted_conditions_vo import ExtractedConditionsVO
from app.exception.question import SavingConditionsUnavailableError
from test.service.saving.saving_fixture import saving, question_api, question_flow


class TestConditionFailure(TestCase):
    def test_자료형_오류는_필드와_기대_자료형을_알린다(self):
        with self.assertRaises(ValidationError) as caught:
            ConditionPredicateVO.model_validate_json(
                '{"field":"autopay","operator":"eq","values":["private response"],'
                '"source_field":"spcl_cnd","source_text":"자동이체"}'
            )
        message = str(ConditionExtractionError.from_error(caught.exception))
        self.assertIn("autopay 조건은 bool 값이 필요하지만 str 값이 반환", message)
        self.assertNotIn("private response", message)

    def test_실패_종류에_맞는_안내를_만든다(self):
        cases: tuple[tuple[Exception, str], ...] = (
            (httpx.ReadTimeout("private response"), "대기 시간"),
            (httpx.ConnectError("private response"), "연결하지 못해"),
            (RuntimeError("private response"), "내부 오류"),
            (ConditionVerificationError("조건의 근거가 공시 원문에 없습니다"), "공시 원문"),
            (ValueError("private response"), "값 검증"),
        )
        for error, expected in cases:
            with self.subTest(error=type(error).__name__):
                message = str(ConditionExtractionError.from_error(error))
                self.assertIn(expected, message)
                self.assertNotIn("private response", message)

    def test_응답_형식_오류를_안내한다(self):
        with self.assertRaises(ValidationError) as caught:
            ExtractedConditionsVO.model_validate_json("{}")
        message = str(ConditionExtractionError.from_error(caught.exception))
        self.assertIn("JSON 형식 또는 조건값", message)

    def test_AI_HTTP_실패에서_외부_본문을_노출하지_않는다(self):
        for status, expected in ((401, "인증"), (403, "인증"), (429, "한도"), (503, "HTTP 503")):
            with self.subTest(status=status):
                error = LlmApiError.from_response(httpx.Response(status, text="private response"))
                self.assertIn(expected, str(error))
                self.assertNotIn("private response", str(error))


class TestConditionFailureLogs(IsolatedAsyncioTestCase):
    async def test_503_로그에_선택기간별_제외_상태와_사유를_남긴다(self):
        missing = saving("bank:missing")
        missing.condition = None
        failed = saving("bank:failed")
        assert failed.condition is not None
        failed.condition.status = ConditionStatus.FAILED
        failed.condition.review_reason = "AI 응답 시간 초과"
        review = saving("bank:review")
        assert review.condition is not None
        review.condition.status = ConditionStatus.NEEDS_REVIEW
        other_term = saving("bank:other", term=24)
        request = AnswerRequestDTO.model_validate_json(
            '{"months":"12","monthly":"none","goal_amount":"none","age":"PRIVATE_ANSWER"}'
        )

        with self.assertLogs("test.question_flow", level="DEBUG") as logs:
            with self.assertRaises(SavingConditionsUnavailableError):
                await question_flow(missing, failed, review, other_term).next_step(request.to_answers())

        output = "\n".join(logs.output)
        self.assertIn("선택기간=(12,) | 조회상품=4 | 조건제외상품=3", output)
        self.assertIn("제외내역=PENDING=1, FAILED=1, NEEDS_REVIEW=1", output)
        self.assertIn("product_id=bank:missing | 저장상태=NO_RECORD", output)
        self.assertIn("product_id=bank:failed | 저장상태=FAILED", output)
        self.assertIn("AI 응답 시간 초과", output)
        self.assertNotIn("bank:other", output)
        self.assertNotIn("PRIVATE_ANSWER", output)


class TestConditionFailureApi(IsolatedAsyncioTestCase):
    async def test_조건_추출_실패_원인을_503으로_알린다(self):
        target = saving()
        assert target.condition is not None
        target.condition.status = ConditionStatus.FAILED
        target.condition.review_reason = "AI 응답 대기 시간을 초과해 상품 조건을 추출하지 못했습니다."

        response = question_api(target).post(
            "/api/v1/questions/next",
            json={"months": "12", "monthly": "none", "goal_amount": "none"},
        )

        self.assertEqual(503, response.status_code)
        self.assertIn("AI 응답 대기 시간을 초과", response.json()["detail"])
