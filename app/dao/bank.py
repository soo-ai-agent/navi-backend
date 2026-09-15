from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

from sqlalchemy import select

from app.model.database.bank import Bank

if TYPE_CHECKING:
    from sqlalchemy import Result, Select
    from sqlalchemy.ext.asyncio import AsyncSession


class BankDao:
    @staticmethod
    async def merge(db: AsyncSession, bank: Bank) -> None:
        await db.merge(bank)

    @staticmethod
    async def list_all(db: AsyncSession, limit: int) -> Sequence[Bank]:
        query: Select[tuple[Bank]] = select(Bank).order_by(Bank.bank_code).limit(limit)
        result: Result[tuple[Bank]] = await db.execute(query)
        return result.scalars().all()
