from __future__ import annotations
from enum import Enum


class JudgeKind(str, Enum):
    """
    받은 답을 어떻게 쓰는가. 코드가 아는 판정 방법은 여기 적힌 것뿐이다.

    LLM 이 공시 원문을 이 중 하나로 분류하고, 판정은 코드가 한다 —
    어디에도 안 맞으면 OTHER 로 두고 원문에서 만든 질문으로 묻는다.
    """

    SAVING_TERM = "SAVING_TERM"
    """저축 기간. 그 기간의 금리 옵션만 비교 대상으로 남긴다"""

    AGE = "AGE"

    FIRST = "FIRST"
    """그 은행과 거래한 적이 없어야 받는다 — 판정이 은행 비교와 반대다"""

    SALARY = "SALARY"

    CARD = "CARD"
    """그 은행 카드를 쓰고, 금액 요건이 있으면 그것도 채우는가"""

    AUTOPAY = "AUTOPAY"

    MOBILE = "MOBILE"

    PRINCIPAL = "PRINCIPAL"
    """만기 원금이 조건의 금액 이상인가"""

    MONTHLY = "MONTHLY"
    """월 납입액이 조건의 금액 이상인가"""

    RANDOM = "RANDOM"
    """추첨·랜덤이라 답할 수 없다 — 언제나 모름으로 둔다"""

    MARKETING = "MARKETING"

    PERFORMANCE_MONTHS = "PERFORMANCE_MONTHS"
    """실적을 채운 달이 조건의 개월 수 이상인가 — "계약기간의 1/2 이상" 같은 요구를 판정한다"""

    PAYMENT_ACCOUNT = "PAYMENT_ACCOUNT"
    """급여·자동이체·카드결제의 출금계좌가 그 은행 계좌인가"""

    OTHER = "OTHER"
    """위 어디에도 속하지 않는 상품 고유 조건. 원문에서 만든 질문으로 묻는다"""
