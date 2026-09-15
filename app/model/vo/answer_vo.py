from __future__ import annotations

from dataclasses import dataclass

from app.enums.answer_value import AnswerStatus


@dataclass(frozen=True)
class AnswerVO:

    key: str
    value: str

    @property
    def status(self) -> AnswerStatus:
        if self.value == AnswerStatus.SKIPPED.value:
            return AnswerStatus.SKIPPED
        return AnswerStatus.PROVIDED
