from __future__ import annotations
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING
from pydantic import BaseModel, ConfigDict
from app.dto.response.ranking import OtherConditionResponseDTO, checklist
from app.enums.saving import MonthlyLimitStatus
from app.enums.saving_condition import ConditionStatus
from app.enums.saving import InterestCalcType, JoinRestriction, ReserveType
from app.model.vo.monthly_limit_vo import MonthlyLimitVO

if TYPE_CHECKING:
    from app.model.database.bank import Bank
    from app.model.database.saving import Saving
    from app.model.vo.banks_vo import BanksVO
    from app.model.vo.saving_products_vo import SavingProductsVO
    from app.model.vo.extracted_conditions_vo import ExtractedConditionsVO


class CatalogRateOptionResponseDTO(BaseModel):
    model_config = ConfigDict(frozen=True, from_attributes=True)

    saving_term_months: int
    reserve_type: ReserveType
    interest_calc_type: InterestCalcType
    base_rate: Decimal
    max_rate: Decimal


class CatalogSavingResponseDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    product_id: str
    bank_code: str
    bank_name: str
    homepage_url: str
    """가입 안내로 보낼 주소. 상품 안내 페이지를 알면 그 주소, 모르면 은행 대표 홈페이지다."""

    call_center: str
    product_name: str
    join_ways: str
    join_member: str
    join_restriction: JoinRestriction
    monthly_limit_status: MonthlyLimitStatus
    monthly_limit: int
    """UNLIMITED일 때 값은 0이며, 한도 유무는 monthly_limit_status로 판정한다."""

    bonus_condition_text: str
    after_maturity_rate_text: str
    etc_note: str
    disclosure_month: str
    disclosure_start_date: date
    rate_options: tuple[CatalogRateOptionResponseDTO, ...]
    condition_status: ConditionStatus
    other_conditions: tuple[OtherConditionResponseDTO, ...]
    other_eligibility_conditions: tuple[OtherConditionResponseDTO, ...]
    other_bonus_conditions: tuple[OtherConditionResponseDTO, ...]

    @classmethod
    def from_saving(cls, saving: Saving, bank: Bank) -> CatalogSavingResponseDTO:
        extracted: ExtractedConditionsVO | ConditionStatus = saving.verified_conditions()

        if isinstance(extracted, ConditionStatus):
            condition_status: ConditionStatus = extracted
            other_conditions: tuple[OtherConditionResponseDTO, ...] = ()
            other_eligibility_conditions: tuple[OtherConditionResponseDTO, ...] = ()
            other_bonus_conditions: tuple[OtherConditionResponseDTO, ...] = ()
        else:
            condition_status = ConditionStatus.EXTRACTED
            other_conditions = checklist(extracted.other_conditions)
            other_eligibility_conditions = checklist(extracted.other_eligibility_conditions)
            other_bonus_conditions = checklist(extracted.other_bonus_conditions)

        monthly_limit: MonthlyLimitVO = MonthlyLimitVO.from_database(saving.monthly_limit)
        return cls(
            product_id=saving.product_id,
            bank_code=bank.bank_code,
            bank_name=bank.display_name,
            homepage_url=saving.homepage_url or bank.homepage_url,
            call_center=bank.call_center,
            product_name=saving.name,
            join_ways=saving.join_ways,
            join_member=saving.join_member,
            join_restriction=saving.join_restriction,
            monthly_limit_status=monthly_limit.status,
            monthly_limit=monthly_limit.amount,
            bonus_condition_text=saving.bonus_condition_text,
            after_maturity_rate_text=saving.after_maturity_rate_text,
            etc_note=saving.etc_note,
            disclosure_month=saving.disclosure_month,
            disclosure_start_date=saving.disclosure_start_date,
            rate_options=tuple(CatalogRateOptionResponseDTO.model_validate(option) for option in saving.rate_options),
            condition_status=condition_status,
            other_conditions=other_conditions,
            other_eligibility_conditions=other_eligibility_conditions,
            other_bonus_conditions=other_bonus_conditions,
        )


class SavingCatalogResponseDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    products: tuple[CatalogSavingResponseDTO, ...]

    @classmethod
    def from_savings(cls, products: SavingProductsVO, banks: BanksVO) -> SavingCatalogResponseDTO:
        return cls(products=tuple(
            CatalogSavingResponseDTO.from_saving(saving, banks.of(saving.bank_code))
            for saving in products.products
        ))
