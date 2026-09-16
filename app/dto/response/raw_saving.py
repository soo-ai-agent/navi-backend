from __future__ import annotations
from datetime import date
from pydantic import BaseModel, ConfigDict
from app.external import disclosure


class RawSavingResponseDTO(BaseModel):
    """공시가 준 적금 상품 한 건. 어드민이 수집 결과를 눈으로 확인한다."""

    model_config = ConfigDict(frozen=True)

    disclosure_month: str
    bank_code: str
    saving_code: str
    bank_name: str
    product_name: str

    join_way: str | None  # 원문 확인용 응답은 공시의 미응답을 그대로 보존한다.

    join_member: str
    join_deny: str
    bonus_condition_text: str
    maturity_interest_text: str
    etc_note: str

    monthly_limit: int | None  # 원문 확인용 응답은 한도 없음의 공시 null을 그대로 보존한다.

    disclosure_start_date: date

    @classmethod
    def from_saving(cls, saving: disclosure.SavingProduct) -> RawSavingResponseDTO:
        return cls(
            disclosure_month=saving.dcls_month,
            bank_code=saving.fin_co_no,
            saving_code=saving.fin_prdt_cd,
            bank_name=saving.kor_co_nm,
            product_name=saving.fin_prdt_nm,
            join_way=saving.join_way,
            join_member=saving.join_member,
            join_deny=saving.join_deny,
            bonus_condition_text=saving.spcl_cnd,
            maturity_interest_text=saving.mtrt_int,
            etc_note=saving.etc_note,
            monthly_limit=saving.max_limit,
            disclosure_start_date=saving.dcls_strt_day,
        )
