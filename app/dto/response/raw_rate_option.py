from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.external.disclosure import SavingProductOption


class RawRateOptionResponseDTO(BaseModel):
    """공시가 준 금리 옵션 한 건. 한 상품에 기간·적립 방식별로 여러 개 붙는다."""

    model_config = ConfigDict(frozen=True)

    bank_code: str
    saving_code: str
    saving_term_months: int
    reserve_type: str
    interest_calc_type: str

    base_rate: float | None
    """기본금리(%) — 금리가 비어 오는 옵션이 실제로 있다"""

    max_rate: float | None

    @classmethod
    def from_option(cls, option: SavingProductOption) -> RawRateOptionResponseDTO:
        return cls(
            bank_code=option.fin_co_no,
            saving_code=option.fin_prdt_cd,
            saving_term_months=option.save_trm,
            reserve_type=option.rsrv_type,
            interest_calc_type=option.intr_rate_type,
            base_rate=option.intr_rate,
            max_rate=option.intr_rate2,
        )
