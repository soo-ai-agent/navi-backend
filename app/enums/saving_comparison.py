from __future__ import annotations

from enum import Enum


class SavingEligibilityStatus(str, Enum):

    ELIGIBLE = "ELIGIBLE"
    NEEDS_CONFIRMATION = "NEEDS_CONFIRMATION"
    NOT_ELIGIBLE = "NOT_ELIGIBLE"


class MaturityEstimateStatus(str, Enum):

    ESTIMATED = "ESTIMATED"
    AMOUNT_REQUIRED = "AMOUNT_REQUIRED"
    INVALID_AMOUNT = "INVALID_AMOUNT"
    MONTHLY_LIMIT_EXCEEDED = "MONTHLY_LIMIT_EXCEEDED"
    INELIGIBLE = "INELIGIBLE"
    CHECK_REQUIRED = "CHECK_REQUIRED"


class GoalReachStatus(str, Enum):

    NO_GOAL = "NO_GOAL"
    REACHED = "REACHED"
    REACHED_AT_MAX_RATE = "REACHED_AT_MAX_RATE"
    SHORT = "SHORT"
