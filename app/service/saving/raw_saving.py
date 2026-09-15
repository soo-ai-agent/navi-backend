from __future__ import annotations

from typing import TYPE_CHECKING

from app.dto.response.raw_savings import RawSavingsResponseDTO

if TYPE_CHECKING:
    from app.external import disclosure
    from app.external.disclosure import DisclosureClient


class RawSavingService:
    _disclosure_client: DisclosureClient

    def __init__(self, disclosure_client: DisclosureClient) -> None:
        self._disclosure_client = disclosure_client

    async def get_savings(self) -> RawSavingsResponseDTO:
        received: disclosure.SavingProducts = await self._disclosure_client.get_saving_products()

        return RawSavingsResponseDTO.from_received(received)
