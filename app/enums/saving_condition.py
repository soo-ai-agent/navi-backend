from __future__ import annotations
from enum import Enum
from typing import assert_never


class ConditionStatus(str, Enum):
    PENDING = "PENDING"
    EXTRACTED = "EXTRACTED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    FAILED = "FAILED"


class ConditionAttemptStatus(str, Enum):
    VALIDATED = "VALIDATED"
    FAILED = "FAILED"


class BonusConditionStatus(str, Enum):
    NO_BONUS = "NO_BONUS"
    AVAILABLE = "AVAILABLE"
    CHECKLIST = "CHECKLIST"
    UNKNOWN = "UNKNOWN"


class ConditionField(str, Enum):
    AGE = "age"
    CUSTOMER_TYPE = "customer_type"
    MONTHLY_DEPOSIT = "monthly_deposit"
    SAVING_TERM = "saving_term"
    PRINCIPAL = "principal"
    SALARY_BANK = "salary_bank"
    EXISTING_BANK = "existing_bank"
    CARD_BANK = "card_bank"
    CARD_SPEND = "card_spend_at_product_bank"
    AUTOPAY = "autopay"
    MOBILE = "mobile"
    MARKETING = "marketing"
    PERFORMANCE_MONTHS = "performance_months"
    PAYMENT_ACCOUNT_BANK = "payment_account_bank"
    OTHER = "other"

    def allowed_operators(self) -> tuple[ConditionOperator, ...]:
        if self.value_type() is int:
            return tuple(ConditionOperator)
        return (ConditionOperator.EQ, ConditionOperator.NE)

    def allowed_text_values(self) -> tuple[str, ...]:
        if self is ConditionField.CUSTOMER_TYPE:
            return ("individual", "business")
        if self in (ConditionField.SALARY_BANK, ConditionField.EXISTING_BANK, ConditionField.CARD_BANK,
                    ConditionField.PAYMENT_ACCOUNT_BANK):
            return (BankAnswer.PRODUCT_BANK.value,)
        raise ValueError("문자열 조건 필드가 아닙니다")

    def value_type(self) -> type[int] | type[str] | type[bool]:
        """외부 조건값을 검증하기 위해 필드가 허용하는 자료형 자체를 반환한다."""
        match self:
            case (ConditionField.AGE | ConditionField.MONTHLY_DEPOSIT | ConditionField.SAVING_TERM
                  | ConditionField.PRINCIPAL | ConditionField.CARD_SPEND | ConditionField.PERFORMANCE_MONTHS):
                return int
            case ConditionField.AUTOPAY | ConditionField.MOBILE | ConditionField.MARKETING | ConditionField.OTHER:
                return bool
            case (ConditionField.CUSTOMER_TYPE | ConditionField.SALARY_BANK | ConditionField.EXISTING_BANK
                  | ConditionField.CARD_BANK | ConditionField.PAYMENT_ACCOUNT_BANK):
                return str
            case _:
                assert_never(self)


BANK_LIST_FIELDS: tuple[ConditionField, ...] = (
    ConditionField.SALARY_BANK, ConditionField.EXISTING_BANK,
    ConditionField.CARD_BANK, ConditionField.PAYMENT_ACCOUNT_BANK,
)
"""은행 목록에서 여러 개를 고르는 질문들. 답 하나를 모든 상품이 함께 쓴다."""

NO_BANK_ANSWER: str = "no_bank"
"""해당하는 은행이 없다는 답. 모른다는 답(AnswerStatus.SKIPPED)과 뜻이 다르다."""


class BankAnswer(str, Enum):
    PRODUCT_BANK = "PRODUCT_BANK"
    """이 상품을 파는 은행이다. AI 조건 추출 규격이 쓰는 값과 같다"""

    NO_BANK = "NO_BANK"


class ConditionOperator(str, Enum):
    EQ = "eq"
    NE = "ne"
    GTE = "gte"
    LTE = "lte"
    BETWEEN = "between"

    def value_count(self) -> int:
        return 2 if self is ConditionOperator.BETWEEN else 1


class ConditionMatch(str, Enum):
    ALL = "all"
    ANY = "any"


class ConditionSourceField(str, Enum):
    JOIN_MEMBER = "join_member"
    BONUS = "spcl_cnd"
    NOTE = "etc_note"
