from __future__ import annotations
from typing import TYPE_CHECKING, Generic, TypeVar
import httpx
from pydantic import BaseModel
from app.external.disclosure.exception import DisclosureApiError
from app.external.disclosure.model import (
    Companies, CompaniesPage, Company, Page, SavingProduct, SavingProductOption, SavingProducts,
    SavingProductsPage
)

if TYPE_CHECKING:
    from typing import AsyncIterator

_TIMEOUT_SECONDS = 30

_OK_ERROR_CODE = "000"
"""공시는 성공도 실패도 HTTP 200 으로 주고 result.err_cd 로만 구분한다"""

PageType = TypeVar("PageType", bound=Page)


class _ApiResult(BaseModel):
    err_cd: str
    err_msg: str


class _ApiResponse(BaseModel):
    result: _ApiResult


class _PageResponse(BaseModel, Generic[PageType]):
    result: PageType


class DisclosureClient:
    """
    공시 접속만 담당한다. 받은 것으로 무엇을 할지는 부르는 쪽이 정한다.

    두 경로 모두 페이지로 나뉘어 오지만, 금융회사는 18곳이고 적금은 59건이라 다 받아 한 번에
    돌려준다 — 부르는 쪽은 페이지를 몰라도 된다.
    """

    _base_url: str
    _bank_group_code: str
    """공시 topFinGrpNo — 금융권역. 우리는 은행 권역(020000)만 부른다"""

    _auth_key: str

    def __init__(self, base_url: str, bank_group_code: str, auth_key: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._bank_group_code = bank_group_code
        self._auth_key = auth_key

    async def get_companies(self) -> Companies:
        companies: list[Company] = []
        async for page in self._get_pages(CompaniesPage):
            companies.extend(page.companies)
        return Companies(companies=tuple(companies))

    async def get_saving_products(self) -> SavingProducts:
        """적금 전체. 공시가 상품과 금리를 따로 주므로 두 목록을 함께 돌려준다."""
        products: list[SavingProduct] = []
        options: list[SavingProductOption] = []

        async for page in self._get_pages(SavingProductsPage):
            products.extend(page.products)
            options.extend(page.options)

        return SavingProducts(products=tuple(products), options=tuple(options))

    async def _get_pages(self, page_type: type[PageType]) -> AsyncIterator[PageType]:
        page_no: int = 1
        while True:
            page: PageType = await self._get_page(page_type, page_no)
            yield page

            if page.is_last():
                return
            page_no += 1

    async def _get_page(self, page_type: type[PageType], page_no: int) -> PageType:
        url: str = f"{self._base_url}/{page_type.path}"
        # HTTP 쿼리 파라미터는 문자열로 전송한다.
        params: tuple[tuple[str, str], ...] = (
            ("auth", self._auth_key),
            ("topFinGrpNo", self._bank_group_code),
            ("pageNo", str(page_no)),
        )

        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            response: httpx.Response = await client.get(url, params=params)

        if response.status_code != httpx.codes.OK:
            raise DisclosureApiError.from_response(response)

        result: _ApiResult = _ApiResponse.model_validate_json(response.content).result
        if result.err_cd != _OK_ERROR_CODE:
            raise DisclosureApiError(result.err_cd, result.err_msg)
        return _PageResponse[page_type].model_validate_json(response.content).result
