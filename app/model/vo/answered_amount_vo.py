from __future__ import annotations
from dataclasses import dataclass
from typing import TypeVar
from app.enums.answer_value import AnswerStatus
from app.model.vo.answers_vo import AnswersVO

_Amount = TypeVar("_Amount", bound="AnsweredAmountVO")


@dataclass(frozen=True)
class AnsweredAmountVO:
    """
    사용자가 숫자로 답한 금액.

    HTTP 로 오는 답은 문자열이라 값을 그대로 믿을 수 없다. 여기서 한 번 검증하고,
    쓸 수 없는 답은 왜 쓸 수 없는지를 status 로 남긴다.
    """

    status: AnswerStatus
    amount: int
    """미응답·입력 오류일 때 금액은 0이며, 유효성은 status 로 구분한다"""

    @classmethod
    def of(cls: type[_Amount], answers: AnswersVO, key: str) -> _Amount:
        answer: str | AnswerStatus = answers.value_of(key)

        if isinstance(answer, AnswerStatus) or answer == "":
            return cls(AnswerStatus.UNANSWERED, 0)

        if not answer.isascii() or not answer.isdecimal() or len(answer) > 18:
            return cls(AnswerStatus.INVALID, 0)

        # HTTP 숫자 답변은 문자열이므로 유효한 숫자만 이 경계에서 정수로 변환한다.
        amount: int = int(answer)
        if amount <= 0:
            return cls(AnswerStatus.INVALID, 0)

        return cls(AnswerStatus.PROVIDED, amount)
