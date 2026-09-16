from __future__ import annotations
from enum import Enum
from typing import assert_never
from app.enums.saving import InterestCalcType, JoinRestriction, ReserveType as SavingReserveType


class ReserveType(str, Enum):
    """공시 rsrv_type — 적립 유형 코드."""

    FIXED = "S"
    FREE = "F"

    def to_reserve_type(self) -> SavingReserveType:
        match self:
            case ReserveType.FIXED:
                return SavingReserveType.FIXED
            case ReserveType.FREE:
                return SavingReserveType.FREE
            case _:
                assert_never(self)


class InterestType(str, Enum):
    """공시 intr_rate_type — 저축 금리 유형 코드."""

    SIMPLE = "S"
    COMPOUND = "M"

    def to_interest_calc_type(self) -> InterestCalcType:
        match self:
            case InterestType.SIMPLE:
                return InterestCalcType.SIMPLE
            case InterestType.COMPOUND:
                return InterestCalcType.COMPOUND
            case _:
                assert_never(self)


class JoinDeny(str, Enum):
    """공시 join_deny — 가입 제한 코드."""

    ANYONE = "1"
    LOW_INCOME_ONLY = "2"
    PARTIAL = "3"

    def to_join_restriction(self) -> JoinRestriction:
        match self:
            case JoinDeny.ANYONE:
                return JoinRestriction.ANYONE
            case JoinDeny.LOW_INCOME_ONLY:
                return JoinRestriction.LOW_INCOME_ONLY
            case JoinDeny.PARTIAL:
                return JoinRestriction.PARTIAL
            case _:
                assert_never(self)
