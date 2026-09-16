from __future__ import annotations
from unittest import IsolatedAsyncioTestCase, TestCase
import httpx
from app.dto.response.saving_catalog import CatalogSavingResponseDTO, SavingCatalogResponseDTO
from app.enums.saving import MonthlyLimitStatus
from app.enums.saving_condition import ConditionStatus
from app.model.database.bank import Bank
from app.model.database.saving import Saving
from app.model.database.saving_condition import SavingCondition
from app.model.vo.banks_vo import BanksVO
from app.model.vo.questions_vo import QuestionsVO
from app.model.vo.saving_products_vo import SavingProductsVO
from test.service.saving.saving_fixture import saving


class TestSavingCatalog(TestCase):
    def test_전체목록은_추출실패_상품을_포함해_10개_이상_반환한다(self) -> None:
        products: tuple[Saving, ...] = tuple(saving(f"bank:P{index}") for index in range(12))
        products[-1].condition = SavingCondition.record(
            products[-1].condition_source(), ConditionStatus.FAILED, "", "응답 검증 실패",
        )
        bank: Bank = Bank(bank_code="bank", display_name="테스트 은행", homepage_url="", call_center="")
        savings_vo: SavingProductsVO = SavingProductsVO(products)
        banks_vo: BanksVO = BanksVO((bank,))

        response: SavingCatalogResponseDTO = SavingCatalogResponseDTO.from_savings(savings_vo, banks_vo)

        self.assertEqual(tuple(item.product_id for item in products), tuple(item.product_id for item in response.products))
        self.assertIs(ConditionStatus.FAILED, response.products[-1].condition_status)

    def test_한도_없음은_null_대신_상태로_반환한다(self) -> None:
        target: Saving = saving()
        target.monthly_limit = None  # 기존 DB의 한도 없는 SQL NULL 상태를 재현한다.
        bank: Bank = Bank(bank_code="bank", display_name="은행", homepage_url="", call_center="")

        response: SavingCatalogResponseDTO = SavingCatalogResponseDTO.from_savings(SavingProductsVO((target,)), BanksVO((bank,)))

        self.assertIs(MonthlyLimitStatus.UNLIMITED, response.products[0].monthly_limit_status)
        self.assertEqual(0, response.products[0].monthly_limit)
        self.assertNotIn(":null", response.model_dump_json())

    def test_상품_안내페이지를_알면_그_주소를_가입_안내로_쓴다(self) -> None:
        target: Saving = saving()
        target.homepage_url = "https://bank.example/savings/1"
        bank: Bank = Bank(bank_code="bank", display_name="은행", homepage_url="https://bank.example/", call_center="")

        response: SavingCatalogResponseDTO = SavingCatalogResponseDTO.from_savings(SavingProductsVO((target,)), BanksVO((bank,)))

        self.assertEqual("https://bank.example/savings/1", response.products[0].homepage_url)

    def test_상품_안내페이지를_모르면_은행_대표_홈페이지를_쓴다(self) -> None:
        target: Saving = saving()
        bank: Bank = Bank(bank_code="bank", display_name="은행", homepage_url="https://bank.example/", call_center="")

        response: SavingCatalogResponseDTO = SavingCatalogResponseDTO.from_savings(SavingProductsVO((target,)), BanksVO((bank,)))

        self.assertEqual("https://bank.example/", response.products[0].homepage_url)


class TestSavingCatalogEndpoint(IsolatedAsyncioTestCase):
    async def test_공개_상품조회는_공시정보와_금리옵션을_반환한다(self) -> None:
        from test.e2e_server import app

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response: httpx.Response = await client.get("/api/v1/products")

        self.assertEqual(200, response.status_code)
        catalog: SavingCatalogResponseDTO = SavingCatalogResponseDTO.model_validate_json(response.content)
        item = catalog.products[0]
        self.assertEqual("테스트 조건", item.join_member)
        self.assertEqual("https://bank.example", item.homepage_url)
        self.assertEqual("1588-0000", item.call_center)
        self.assertEqual(12, item.rate_options[0].saving_term_months)
        self.assertEqual("SIMPLE", item.rate_options[0].interest_calc_type.value)


class TestSavingDetailEndpoint(IsolatedAsyncioTestCase):
    async def test_상품_상세는_목록과_같은_상품_필드를_반환한다(self) -> None:
        from test.e2e_server import app

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response: httpx.Response = await client.get("/api/v1/products/bank:P1")

        self.assertEqual(200, response.status_code)
        item: CatalogSavingResponseDTO = CatalogSavingResponseDTO.model_validate_json(response.content)
        self.assertEqual("bank:P1", item.product_id)
        self.assertEqual("테스트 조건", item.join_member)
        self.assertEqual("https://bank.example", item.homepage_url)
        self.assertEqual(12, item.rate_options[0].saving_term_months)

    async def test_없는_상품_상세는_404를_반환한다(self) -> None:
        from test.e2e_server import app

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response: httpx.Response = await client.get("/api/v1/products/bank:NOPE")

        self.assertEqual(404, response.status_code)
