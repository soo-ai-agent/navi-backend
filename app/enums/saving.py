from __future__ import annotations
from enum import Enum


class BonusResult(str, Enum):

    ELIGIBLE = "ELIGIBLE"
    NOT_ELIGIBLE = "NOT_ELIGIBLE"
    UNKNOWN = "UNKNOWN"
    """아직 안 물어봐서 판단 불가 — 질문 후보가 된다"""


class ReserveType(str, Enum):

    FIXED = "FIXED"
    """매달 같은 금액"""

    FREE = "FREE"
    """원할 때 원하는 금액"""


class InterestCalcType(str, Enum):

    SIMPLE = "SIMPLE"
    """단리"""

    COMPOUND = "COMPOUND"
    """복리"""


class JoinRestriction(str, Enum):

    ANYONE = "ANYONE"
    LOW_INCOME_ONLY = "LOW_INCOME_ONLY"
    """서민 전용"""

    PARTIAL = "PARTIAL"
    """일부 제한 — 나이·직업 등 상품마다 다르다"""


class MonthlyLimitStatus(str, Enum):

    LIMITED = "LIMITED"
    UNLIMITED = "UNLIMITED"
