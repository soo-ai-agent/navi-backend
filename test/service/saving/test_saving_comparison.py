from __future__ import annotations

from unittest import IsolatedAsyncioTestCase, TestCase

import httpx

from app.dto.response.saving_comparison import SavingComparisonsResponseDTO
from app.enums.saving_comparison import MaturityEstimateStatus, SavingEligibilityStatus
from app.model.database.saving import Saving
from app.model.vo.banks_vo import BanksVO
from app.model.vo.questions_vo import QuestionsVO
from app.model.vo.saving_products_vo import SavingProductsVO
from test.service.saving.saving_fixture import answers, group, predicate, saving


class TestSavingComparisons(TestCase):
    def test_모든_상품을_기간과_가입불가로_제외하지_않는다(self) -> None:
        products: tuple[Saving, ...] = tuple(
            saving(f"bank:P{index}", term=24, eligibility=group(predicate())) for index in range(12)
        )

        response: SavingComparisonsResponseDTO = SavingComparisonsResponseDTO.from_savings(
            SavingProductsVO(products), answers(("monthly", "300000"), ("months", "12"), ("age", "18")),
        )

        self.assertEqual(tuple(target.product_id for target in products), tuple(item.product_id for item in response.products))
        self.assertTrue(all(item.options[0].eligibility_status is SavingEligibilityStatus.NOT_ELIGIBLE for item in response.products))


class TestSavingComparisonEndpoint(IsolatedAsyncioTestCase):
    async def test_비교_API는_문자열_답변으로_개인금리와_null없는_예상액을_반환한다(self) -> None:
        from test.e2e_server import app

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response: httpx.Response = await client.post(
                "/api/v1/products/compare", content='{"monthly":"300000","age":"25","salary_bank:bank":"yes"}',
                headers={"Content-Type": "application/json"},
            )

        self.assertEqual(200, response.status_code)
        comparison: SavingComparisonsResponseDTO = SavingComparisonsResponseDTO.model_validate_json(response.content)
        self.assertIs(MaturityEstimateStatus.ESTIMATED, comparison.products[0].options[0].estimate.status)
        self.assertNotIn(":null", comparison.model_dump_json())
