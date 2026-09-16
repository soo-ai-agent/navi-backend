from __future__ import annotations
from typing import TYPE_CHECKING, Sequence
from sqlalchemy import select
from app.model.database.question import Question

if TYPE_CHECKING:
    from sqlalchemy import Result, Select
    from sqlalchemy.ext.asyncio import AsyncSession


class QuestionDao:
    @staticmethod
    async def list_all(db: AsyncSession, limit: int) -> Sequence[Question]:
        query: Select[tuple[Question]] = (
            select(Question)
            .order_by(Question.ask_order, Question.code)
            .limit(limit)
        )
        result: Result[tuple[Question]] = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def merge(db: AsyncSession, question: Question) -> None:
        await db.merge(question)
