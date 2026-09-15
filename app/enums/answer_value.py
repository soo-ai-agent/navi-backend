from __future__ import annotations

from enum import Enum


class YesNoAnswer(str, Enum):

    YES = "yes"
    NO = "no"


class AnswerStatus(Enum):
    PROVIDED = "PROVIDED"
    UNANSWERED = "UNANSWERED"
    SKIPPED = "none"
    """답을 모르거나 건너뛴 경우. 기간은 제한하지 않고 미확인 우대는 가산하지 않는다."""
    INVALID = "INVALID"
