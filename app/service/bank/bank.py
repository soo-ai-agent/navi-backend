from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

from app.model.vo.banks_vo import BanksVO

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from app.dao.bank import BankDao
    from app.model.database.bank import Bank

_LIMIT = 1000
"""은행은 18곳뿐이다 — 데이터가 예상 밖으로 늘었을 때를 막는 상한이다"""


class BankService:
    _async_session_maker: async_sessionmaker[AsyncSession]
    _bank_dao: BankDao

    def __init__(
            self,
            async_session_maker: async_sessionmaker[AsyncSession],
            bank_dao: BankDao,
    ) -> None:
        self._async_session_maker = async_session_maker
        self._bank_dao = bank_dao

    async def get(self, request_id: str = "background") -> BanksVO:
        return BanksVO(banks=tuple(await self.list_all()))

    def clear(self) -> None:
        """보관하는 것이 없어 버릴 것도 없다."""

    async def list_all(self) -> Sequence[Bank]:
        async with self._async_session_maker() as session:
            return await self._bank_dao.list_all(session, limit=_LIMIT)

    async def save_all(self, banks: Sequence[Bank]) -> None:
        async with self._async_session_maker() as session:
            async with session.begin():
                for bank in banks:
                    await self._bank_dao.merge(session, bank)
