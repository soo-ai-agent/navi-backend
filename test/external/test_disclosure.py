from __future__ import annotations
import json
from functools import partial
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch
import httpx
from app.external.disclosure import DisclosureApiError, DisclosureClient, SavingProducts

_PRODUCT = {
    "dcls_month": "202609", "fin_co_no": "0010001", "fin_prdt_cd": "P1",
    "kor_co_nm": "테스트은행", "fin_prdt_nm": "테스트적금", "join_way": "인터넷",
    "join_member": "제한없음", "join_deny": "1", "spcl_cnd": "급여이체 시 우대",
    "mtrt_int": "만기 후 50%", "etc_note": "-", "max_limit": 500000, "dcls_strt_day": "20260901",
}

_OPTION = {
    "fin_co_no": "0010001", "fin_prdt_cd": "P1", "save_trm": "12",
    "rsrv_type": "S", "intr_rate_type": "S", "intr_rate": 3.0, "intr_rate2": 3.5,
}


# 누락·오류가 있는 외부 JSON을 재현해야 하므로 테스트 응답은 dict로 만든다.
def _page(now_page_no: int, max_page_no: int) -> dict:
    return {
        "result": {
            "err_cd": "000", "err_msg": "정상",
            "now_page_no": now_page_no, "max_page_no": max_page_no,
            "baseList": [_PRODUCT], "optionList": [_OPTION],
        }
    }


class TestGetSavingProducts(IsolatedAsyncioTestCase):
    """공시 응답을 흉내 내는 전송 계층을 끼워 페이지 넘김과 오류 번역만 확인한다."""

    async def _get(self, responses: list[dict]) -> SavingProducts:
        self.requested_page_numbers: list[str] = []

        def handle(request: httpx.Request) -> httpx.Response:
            page_no = httpx.QueryParams(request.url.query)["pageNo"]
            self.requested_page_numbers.append(page_no)
            return httpx.Response(200, content=json.dumps(responses[int(page_no) - 1]))

        client = DisclosureClient("https://finlife.test", "020000", "test-key")
        with patch.object(
            httpx, "AsyncClient", partial(httpx.AsyncClient, transport=httpx.MockTransport(handle))
        ):
            return await client.get_saving_products()

    async def test_마지막_페이지까지_돈다(self):
        await self._get([_page(1, 2), _page(2, 2)])

        self.assertEqual(["1", "2"], self.requested_page_numbers)

    async def test_페이지들을_한_결과로_모은다(self):
        received = await self._get([_page(1, 2), _page(2, 2)])

        self.assertEqual(2, len(received.products))
        self.assertEqual(2, len(received.options))

    async def test_오류_코드는_예외로_바꾼다(self):
        error_response = {"result": {"err_cd": "020", "err_msg": "일일 허용 횟수 초과"}}

        with self.assertRaises(DisclosureApiError) as ctx:
            await self._get([error_response])
        self.assertIn("020", str(ctx.exception))
