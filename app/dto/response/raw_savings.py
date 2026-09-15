from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.external.disclosure import SavingProducts

from app.dto.response.raw_rate_option import RawRateOptionResponseDTO
from app.dto.response.raw_saving import RawSavingResponseDTO


class RawSavingsResponseDTO(BaseModel):
    """적금 공시 수신 결과 전체. 공시는 상품과 금리 옵션을 따로 준다."""

    model_config = ConfigDict(frozen=True)

    products: tuple[RawSavingResponseDTO, ...]
    options: tuple[RawRateOptionResponseDTO, ...]

    @classmethod
    def from_received(cls, received: SavingProducts) -> RawSavingsResponseDTO:
        return cls(
            products=tuple(RawSavingResponseDTO.from_saving(saving) for saving in received.products),
            options=tuple(RawRateOptionResponseDTO.from_option(option) for option in received.options),
        )
