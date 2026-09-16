from __future__ import annotations
from typing import TYPE_CHECKING, Sequence
from app.model.vo.questions_vo import QuestionsVO

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from app.dao.question import QuestionDao
    from app.model.database.question import Question

_LIMIT = 1000
"""한 번에 조회할 질문 수. 고정 질문과 우대조건 질문을 합쳐도 수십 건이다"""


class QuestionService:
    _async_session_maker: async_sessionmaker[AsyncSession]
    _question_dao: QuestionDao

    def __init__(
            self,
            async_session_maker: async_sessionmaker[AsyncSession],
            question_dao: QuestionDao,
    ) -> None:
        self._async_session_maker = async_session_maker
        self._question_dao = question_dao

    async def get(self, request_id: str = "background") -> QuestionsVO:
        return QuestionsVO(questions=tuple(await self.list_all()))

    def clear(self) -> None:
        """보관하는 것이 없어 버릴 것도 없다."""

    async def list_all(self) -> Sequence[Question]:
        async with self._async_session_maker() as session:
            return await self._question_dao.list_all(session, limit=_LIMIT)

    async def save_missing(self, questions: Sequence[Question]) -> None:
        async with self._async_session_maker() as session:
            async with session.begin():
                saved: Sequence[Question] = await self._question_dao.list_all(session, limit=_LIMIT)

                saved_codes: set[str] = set()
                for question in saved:
                    saved_codes.add(question.code)

                for question in questions:
                    if question.code in saved_codes:
                        continue
                    await self._question_dao.merge(session, question)
