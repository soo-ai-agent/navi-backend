from __future__ import annotations

from app.enums.answer_value import AnswerStatus, YesNoAnswer

YES_NO_OPTIONS: tuple[tuple[str, str], ...] = (
    (YesNoAnswer.YES, "네"),
    (YesNoAnswer.NO, "아니요"),
)

MONTHLY_DEPOSIT_OPTIONS: tuple[tuple[str, str], ...] = (
    ("100000", "10만원"),
    ("300000", "30만원"),
    ("500000", "50만원"),
    ("1000000", "100만원"),
)

AGE_OPTIONS: tuple[tuple[str, str], ...] = (
    ("18", "18세"), ("20", "20세"), ("30", "30세"),
    ("40", "40세"), ("50", "50세"), ("60", "60세"),
)

UNKNOWN_OPTION: tuple[tuple[str, str], ...] = ((AnswerStatus.SKIPPED.value, "모르겠어요"),)
"""숫자를 답할 수 없을 때 고르는 선택지. 건너뛴 답과 같게 다룬다."""

GOAL_AMOUNT_KEY: str = "goal_amount"
"""만기 목표 금액 답변의 키. 우대조건 판정에는 쓰이지 않고 달성 여부 안내에만 쓴다."""

PRINCIPAL_OPTIONS: tuple[tuple[str, str], ...] = (
    ("1000000", "100만원"), ("3000000", "300만원"),
    ("5000000", "500만원"), ("10000000", "1,000만원"),
)

PERFORMANCE_MONTHS_OPTIONS: tuple[tuple[str, str], ...] = (
    ("3", "3개월"),
    ("6", "6개월"),
    ("12", "12개월"),
    ("24", "24개월"),
)

CARD_SPEND_OPTIONS: tuple[tuple[str, str], ...] = (
    ("0", "0원"), ("300000", "30만원"),
    ("500000", "50만원"), ("1000000", "100만원"),
)
