from __future__ import annotations

from dataclasses import dataclass

from app.enums.answer_value import AnswerStatus
from app.model.vo.answer_vo import AnswerVO


@dataclass(frozen=True)
class AnswersVO:
    entries: tuple[AnswerVO, ...] = ()

    def value_of(self, key: str) -> str | AnswerStatus:
        for answer in self.entries:
            if answer.key != key:
                continue
            if answer.status is AnswerStatus.SKIPPED:
                return AnswerStatus.SKIPPED
            return answer.value
        return AnswerStatus.UNANSWERED

    def contains(self, key: str) -> bool:
        return any(answer.key == key for answer in self.entries)
