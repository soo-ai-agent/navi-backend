from __future__ import annotations
from typing import TYPE_CHECKING
from infra.request_context import current_request_id, short_request_id
from app.dto.response.saving_refresh import DisclosureSyncResponseDTO

if TYPE_CHECKING:
    from logging import Logger

    from app.external import disclosure
    from app.external.disclosure import DisclosureClient
    from app.model.database.bank import Bank
    from app.model.database.saving import Saving
    from app.model.database.rate_option import RateOption
    from app.service.bank.bank import BankService
    from app.service.saving.saving import SavingService


class DisclosureSyncService:
    """
    금감원 공시를 받아 DB 에 적재한다. 한 달에 한 번 손으로 돌리는 배치다
    (흐름 1 — docs/external-data-sources.md).

    흐름만 조립한다 — 우리 Entity 로 옮기는 것은 공시 모델이, 재번역이 필요한지는 상품이,
    저장은 은행·상품 서비스가 각자 판단한다. 우대조건 구조화(AI)는 다음 단계이며, 여기서는
    원문과 해시만 저장한다.
    """

    _disclosure_client: DisclosureClient
    _saving_service: SavingService
    _bank_service: BankService
    _logger: Logger

    def __init__(
            self,
            disclosure_client: DisclosureClient,
            saving_service: SavingService,
            bank_service: BankService,
            logger: Logger,
    ) -> None:
        self._disclosure_client = disclosure_client
        self._saving_service = saving_service
        self._bank_service = bank_service
        self._logger = logger

    async def sync(self) -> DisclosureSyncResponseDTO:
        companies: disclosure.Companies = await self._disclosure_client.get_companies()
        received: disclosure.SavingProducts = await self._disclosure_client.get_saving_products()

        banks: list[Bank] = companies.to_banks()
        await self._bank_service.save_all(banks)

        products: list[Saving] = received.to_savings()
        bonus_reset_savings: int = await self._saving_service.save_all(products)

        options: list[RateOption] = received.to_rate_options()
        skipped: int = len(received.options) - len(options)
        if skipped > 0:
            self._logger.warning("금리 없는 옵션 제외 | req=%s | 옵션수=%d", short_request_id(), skipped)
        saving_ids: list[str] = [saving.product_id for saving in products]
        rate_options: int = await self._saving_service.replace_rate_options(options, saving_ids)
        await self._saving_service.invalidate_changed_conditions()

        result: DisclosureSyncResponseDTO = DisclosureSyncResponseDTO(
            banks=len(banks),
            products=len(products),
            rate_options=rate_options,
            bonus_reset_savings=bonus_reset_savings,
        )
        self._logger.info(
            "공시 적재 완료 | req=%s | 은행=%d | 상품=%d | 금리옵션=%d | 재번역대상=%d",
            short_request_id(), result.banks, result.products, result.rate_options, result.bonus_reset_savings,
        )
        return result
