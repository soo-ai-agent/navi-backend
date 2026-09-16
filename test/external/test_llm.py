from __future__ import annotations
from functools import partial
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch
import httpx
from pydantic import ValidationError
from app.external.llm import ChatMessage, LlmClient, LlmApiError
from app.external.llm.model import ChatRequest


class TestLlmClient(IsolatedAsyncioTestCase):
    sent: ChatRequest
    content_type: str

    async def request(self, body: str, status: int = 200) -> str:
        def respond(request: httpx.Request) -> httpx.Response:
            self.sent = ChatRequest.model_validate_json(request.content)
            self.content_type = request.headers["content-type"]
            return httpx.Response(status, text=body)
        with patch.object(httpx, "AsyncClient", partial(httpx.AsyncClient, transport=httpx.MockTransport(respond))):
            return await LlmClient("https://llm.test", "test", "test-model").ask_json((ChatMessage(role="user", content="조건"),))

    async def test_요청과_응답을_타입모델로_처리한다(self):
        content = await self.request('{"choices":[{"message":{"role":"assistant","content":"{}"}}]}')
        self.assertEqual("{}", content)
        self.assertEqual("test-model", self.sent.model)
        self.assertEqual("json_object", self.sent.response_format.type)
        self.assertEqual("application/json", self.content_type)

    async def test_빈_응답_선택지는_거부한다(self):
        with self.assertRaises(ValidationError):
            await self.request('{"choices": []}')

    async def test_HTTP_실패를_도메인_오류로_변환한다(self):
        with self.assertRaises(LlmApiError):
            await self.request('failure', status=500)
