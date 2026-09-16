"""
금감원 공시 응답 모델. 낱말과 매핑 방향은 disclosure/__init__.py 를 본다.

err_cd·err_msg 는 DisclosureClient 의 응답 모델에서 성공·실패 판별에 쓴다.
쓰지 않는 키(prdt_div·dcls_chrg_man·intr_rate_type_nm 등)는 적지 않는다 — 응답에
있어도 Pydantic 이 버린다.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime
import hashlib
import re
from decimal import Decimal
from typing import ClassVar
from pydantic import BaseModel, Field, field_validator
from app.external.disclosure.code import InterestType, JoinDeny, ReserveType
from app.model.database.bank import Bank
from app.model.database.saving import Saving
from app.model.database.rate_option import RateOption

_COMPACT_DATE_FORMAT = "%Y%m%d"

_COMPANY_SUFFIX_PATTERN = re.compile(r"주식회사|㈜")

_NO_LIMIT_SENTINEL = 999999999
"""공시가 '한도 없음'을 이 숫자로 표현하는 상품이 있다 (경남은행 행복DREAM 등)"""

_NONE_WORDS = frozenset({"없음", "해당없음", "해당 없음", "-", ""})
"""우대조건이 없는 상품이 공시에 적어 보내는 말들"""



def hash_of(bonus_condition_text: str) -> str:
    return hashlib.sha256(bonus_condition_text.encode()).hexdigest()


def _single_line(text: str) -> str:
    return ' '.join(text.split())


class Company(BaseModel):
    """
    금융회사 한 곳. companySearch.json 의 baseList 항목 하나다.

        {
          "dcls_month": "202608",
          "fin_co_no": "0010001",
          "kor_co_nm": "우리은행",
          "dcls_chrg_man": "개인상품마케팅부, 1588-5000\\n부동산금융부, 1588-5000",
          "homp_url": "https://spot.wooribank.com/pot/Dream?withyou=po",
          "cal_tel": "15885000"
        }
    """

    fin_co_no: str
    kor_co_nm: str
    homp_url: str | None  # 공시에 홈페이지가 없는 상품이 있어 외부 응답 경계에서만 선택값이다.
    cal_tel: str | None  # 공시에 상담전화가 없는 상품이 있어 외부 응답 경계에서만 선택값이다.

    def to_bank(self) -> Bank:
        return Bank(
            bank_code=self.fin_co_no,
            original_name=self.kor_co_nm,
            display_name=_COMPANY_SUFFIX_PATTERN.sub('', self.kor_co_nm).strip(),
            homepage_url=self.homp_url or '',
            call_center=self.cal_tel or '',
        )


class SavingProduct(BaseModel):
    """
    적금 상품 한 건. savingProductsSearch.json 의 baseList 항목 하나다.

        {
          "dcls_month": "202608",
          "fin_co_no": "0010001",
          "fin_prdt_cd": "WR0001F",
          "kor_co_nm": "우리은행",
          "fin_prdt_nm": "우리SUPER주거래적금",
          "join_way": "영업점,인터넷,스마트폰,전화(텔레뱅킹)",
          "mtrt_int": "만기 후\\n- 1개월이내 : 만기시점약정이율×50%\\n...",
          "spcl_cnd": "1.우리은행 입출식 계좌에서...\\n가.급여/연금 이체:연 0.7%p\\n...",
          "join_deny": "1",
          "join_member": "실명의 개인",
          "etc_note": "1. 가입기간 : 1년/2년/3년\\n2. 가입금액 : 월 50만원 이내",
          "max_limit": null,
          "dcls_strt_day": "20260820",
          "dcls_end_day": null,
          "fin_co_subm_day": "202608201532"
        }

    금리는 여기 없다 — 기간·적립방식마다 달라 SavingProductOption 이 따로 온다.
    """

    dcls_month: str
    fin_co_no: str
    fin_prdt_cd: str
    kor_co_nm: str
    fin_prdt_nm: str
    join_way: str | None  # 가입 방법이 비어 오는 공시가 있어 내부 Product에서는 빈 문자열로 정규화한다.
    join_member: str
    join_deny: JoinDeny
    spcl_cnd: str
    mtrt_int: str
    etc_note: str
    max_limit: int | None  # 외부 공시가 한도 없음 또는 미응답을 null로 보낸다.
    dcls_strt_day: date
    """공시 시작일. 공시는 YYYYMMDD 문자열로 주지만 날짜로 받는다"""

    @field_validator("dcls_strt_day", mode="before")
    @classmethod
    def _parse_compact_date(cls, value: str) -> date:
        """공시는 구분자 없는 YYYYMMDD 를 준다 — Pydantic 이 못 읽으므로 직접 읽는다."""
        return datetime.strptime(value, _COMPACT_DATE_FORMAT).date()

    def to_saving(self) -> Saving:
        bonus_condition_text: str = self._bonus_condition_text()

        return Saving(
            product_id=Saving.id_of(self.fin_co_no, self.fin_prdt_cd),
            bank_code=self.fin_co_no,
            name=_single_line(self.fin_prdt_nm),
            join_ways=self.join_way or '',
            join_member=_single_line(self.join_member),
            join_restriction=self.join_deny.to_join_restriction(),
            monthly_limit=self._monthly_limit(),
            bonus_condition_text=bonus_condition_text,
            bonus_source_hash=hash_of(bonus_condition_text),
            after_maturity_rate_text=self.mtrt_int.strip(),
            etc_note=self.etc_note.strip(),
            disclosure_month=f"{self.dcls_month[:4]}-{self.dcls_month[4:]}",
            disclosure_start_date=self.dcls_strt_day,
        )

    def _bonus_condition_text(self) -> str:
        text: str = self.spcl_cnd.strip()
        if text in _NONE_WORDS:
            return ''
        return text

    def _monthly_limit(self) -> int | None:
        if self.max_limit is None or self.max_limit >= _NO_LIMIT_SENTINEL:
            return None
        return self.max_limit


class SavingProductOption(BaseModel):
    """
    적금 금리 한 건. savingProductsSearch.json 의 optionList 항목 하나다.

        {
          "dcls_month": "202608",
          "fin_co_no": "0010001",
          "fin_prdt_cd": "WR0001F",
          "intr_rate_type": "S", "intr_rate_type_nm": "단리",
          "rsrv_type": "F", "rsrv_type_nm": "자유적립식",
          "save_trm": "12",
          "intr_rate": 2.45,
          "intr_rate2": 3.85
        }

    상품과는 (fin_co_no, fin_prdt_cd) 로 이어진다 — 한 상품에 기간·적립방식별로 여러 건이
    붙는다. 이름이 붙은 `_nm` 키는 코드와 같은 값이라 읽지 않는다.
    """

    fin_co_no: str
    fin_prdt_cd: str
    save_trm: int
    """저축 기간(개월). 공시는 문자열로 주지만 숫자로 받는다"""

    rsrv_type: ReserveType
    intr_rate_type: InterestType

    intr_rate: float | None
    """기본금리 — 금리가 비어 있는 옵션이 실제로 있다. None 이면 계산에서 뺀다"""

    intr_rate2: float | None  # 공시 금리 누락은 순위 계산에서 제외해야 하므로 외부 경계에서만 선택값이다.

    def to_rate_option(self) -> RateOption | None:
        """
        우리 금리 옵션으로 옮긴다. 금리가 비어 있으면 순위 계산에 쓸 수 없어 None 이다
        (공시에 실제로 존재한다 — docs/external-data-sources.md 주의할 점).

        금리는 더하고 비교해 순위를 가르므로 부동소수점 오차가 남지 않게 Decimal 로 고정한다.
        """
        if self.intr_rate is None or self.intr_rate2 is None:
            return None

        # 공시의 float 금리를 십진 문자열을 거쳐 Decimal로 바꿔 이진 소수 오차가 저장되지 않게 한다.
        return RateOption(
            product_id=Saving.id_of(self.fin_co_no, self.fin_prdt_cd),
            saving_term_months=self.save_trm,
            reserve_type=self.rsrv_type.to_reserve_type(),
            interest_calc_type=self.intr_rate_type.to_interest_calc_type(),
            base_rate=Decimal(str(self.intr_rate)),
            max_rate=Decimal(str(self.intr_rate2)),
        )


class Page(BaseModel):
    """
    응답의 result 한 페이지. 두 경로가 공통으로 주는 페이지 번호만 읽는다.

        {"result": {
          "prdt_div": "S", "total_count": 59,
          "max_page_no": 1, "now_page_no": 1,
          "err_cd": "000", "err_msg": "정상",
          ...목록...
        }}

    어느 경로가 이 모양을 주는지는 하위 클래스의 path 가 안다.
    """

    path: ClassVar[str]

    now_page_no: int
    max_page_no: int

    def is_last(self) -> bool:
        return self.now_page_no >= self.max_page_no


class SavingProductsPage(Page):
    """
    적금 API 한 페이지. 공시는 상품과 금리를 두 목록으로 나눠 준다.

        {"result": {..., "baseList": [SavingProduct...], "optionList": [SavingProductOption...]}}
    """

    path: ClassVar[str] = "savingProductsSearch.json"

    products: tuple[SavingProduct, ...] = Field(alias="baseList")
    options: tuple[SavingProductOption, ...] = Field(alias="optionList")


class CompaniesPage(Page):
    path: ClassVar[str] = "companySearch.json"

    companies: tuple[Company, ...] = Field(alias="baseList")


@dataclass(frozen=True)
class Companies:
    """금융회사 공시 수신 결과 전체 — 페이지를 다 넘긴 뒤의 모습이다."""

    companies: tuple[Company, ...]

    def to_banks(self) -> list[Bank]:
        banks: list[Bank] = []
        for company in self.companies:
            banks.append(company.to_bank())
        return banks


@dataclass(frozen=True)
class SavingProducts:
    """
    적금 공시 수신 결과 전체 — 페이지를 다 넘긴 뒤의 모습이다.

    공시가 상품과 금리를 두 목록으로 나눠 주므로 둘을 함께 들고 다닌다. 이어 붙이는 열쇠는
    (fin_co_no, fin_prdt_cd) 다.
    """

    products: tuple[SavingProduct, ...]
    options: tuple[SavingProductOption, ...]

    def to_savings(self) -> list[Saving]:
        products: list[Saving] = []
        for raw_saving in self.products:
            products.append(raw_saving.to_saving())
        return products

    def to_rate_options(self) -> list[RateOption]:
        options: list[RateOption] = []
        for raw_option in self.options:
            option: RateOption | None = raw_option.to_rate_option()
            if option is not None:
                options.append(option)
        return options
