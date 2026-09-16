from __future__ import annotations
from dataclasses import dataclass
from app.model.database.question import Question


@dataclass(frozen=True)
class QuestionsVO:
    questions: tuple[Question, ...]

    def title(self, code: str, default: str) -> str:
        for question in self.questions:
            if question.code == code:
                return question.title
        return default
