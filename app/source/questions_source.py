from __future__ import annotations
from typing import Protocol
from app.model.vo.questions_vo import QuestionsVO


class QuestionsSource(Protocol):
    async def get(self, request_id: str = "background") -> QuestionsVO: ...

    def clear(self) -> None: ...
