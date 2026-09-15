from __future__ import annotations

from typing import TYPE_CHECKING

from infra.request_context import current_request_id, short_request_id
from app.dto.response.saving_catalog import CatalogSavingResponseDTO, SavingCatalogResponseDTO
from app.dto.response.saving_comparison import SavingComparisonsResponseDTO
from app.exception.saving import SavingNotFoundError

if TYPE_CHECKING:
    from logging import Logger

    from app.model.vo.answers_vo import AnswersVO
    from app.model.vo.banks_vo import BanksVO
    from app.model.vo.saving_products_vo import SavingProductsVO
    from app.source.banks_source import BanksSource
    from app.source.saving_products_source import SavingProductsSource


class SavingCatalogService:
    _savings_source: SavingProductsSource
    _bank_service: BanksSource
    _logger: Logger

    def __init__(
            self, savings_source: SavingProductsSource, bank_service: BanksSource, logger: Logger,
    ) -> None:
        self._savings_source = savings_source
        self._bank_service = bank_service
        self._logger = logger

    async def catalog(self) -> SavingCatalogResponseDTO:
        request_id: str = current_request_id()
        self._logger.debug("상품 목록 조회 시작 | req=%s", short_request_id(request_id))
        products: SavingProductsVO = await self._savings_source.get(request_id)
        banks: BanksVO = await self._bank_service.get(request_id)

        response: SavingCatalogResponseDTO = SavingCatalogResponseDTO.from_savings(products, banks)
        self._logger.info("상품 목록 조회 완료 | req=%s | 상품수=%d", short_request_id(request_id), len(response.products))
        return response

    async def compare(self, answers: AnswersVO) -> SavingComparisonsResponseDTO:
        request_id: str = current_request_id()
        self._logger.debug("상품 비교 시작 | req=%s | 답변수=%d", short_request_id(request_id), len(answers.entries))
        products: SavingProductsVO = await self._savings_source.get(request_id)

        response: SavingComparisonsResponseDTO = SavingComparisonsResponseDTO.from_savings(products, answers)
        self._logger.info("상품 비교 완료 | req=%s | 상품수=%d", short_request_id(request_id), len(response.products))
        return response

    async def detail(self, product_id: str) -> CatalogSavingResponseDTO:
        request_id: str = current_request_id()
        self._logger.debug("상품 상세 조회 시작 | req=%s | product_id=%s", short_request_id(request_id), product_id)
        products: SavingProductsVO = await self._savings_source.get(request_id)

        for saving in products.products:
            if saving.product_id == product_id:
                banks: BanksVO = await self._bank_service.get(request_id)
                response: CatalogSavingResponseDTO = CatalogSavingResponseDTO.from_saving(
                    saving, banks.of(saving.bank_code),
                )
                self._logger.info(
                    "상품 상세 조회 완료 | req=%s | product_id=%s | 금리옵션수=%d",
                    short_request_id(request_id), product_id, len(response.rate_options),
                )
                return response

        raise SavingNotFoundError(f"상품을 찾을 수 없습니다: {product_id}")
