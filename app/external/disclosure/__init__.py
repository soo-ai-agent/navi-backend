"""금감원 금융상품 통합 비교공시 접속.

낱말은 공시가 쓰는 것을 그대로 쓴다 — 여기서는 은행을 `Company`(금융회사), 적금을
`SavingProduct` 라 부른다. 우리 낱말(`Bank`·`Product`)로 바꾸는 일은 그 필드를 가진 모델이
직접 한다 — 공시 필드가 바뀌면 고칠 곳이 그 모델 하나다.

    disclosure.Company             .to_bank()         ──▶ Bank
    disclosure.SavingProduct       .to_product()      ──▶ Product
    disclosure.SavingProductOption .to_rate_option()  ──▶ RateOption | None

수신 결과 전체를 한 번에 옮기는 것도 그 결과가 안다.

    disclosure.Companies           .to_banks()        ──▶ list[Bank]
    disclosure.SavingProducts      .to_products()     ──▶ list[Product]
                                   .to_rate_options() ──▶ list[RateOption]

쓰는 쪽은 모듈째 import 해 `disclosure.SavingProduct` 로 부른다 — 공시가 준 원본이라는 것이
호출부에서 드러난다.
"""

from __future__ import annotations
from app.external.disclosure.api import DisclosureClient
from app.external.disclosure.code import InterestType, JoinDeny, ReserveType
from app.external.disclosure.exception import DisclosureApiError
from app.external.disclosure.model import (
    Companies, CompaniesPage, Company, SavingProduct, SavingProductOption, SavingProducts,
    SavingProductsPage, hash_of
)

__all__ = [
    "Companies", "CompaniesPage", "Company", "DisclosureApiError", "DisclosureClient",
    "InterestType", "JoinDeny", "ReserveType", "SavingProduct", "SavingProductOption",
    "SavingProducts", "SavingProductsPage", "hash_of",
]
