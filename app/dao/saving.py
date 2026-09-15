from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from app.model.database.saving_bonus import SavingBonus
from app.model.database.rate_option import RateOption
from app.model.database.saving import Saving
from app.model.database.saving_condition import SavingCondition
from app.model.database.saving_condition_attempt import SavingConditionAttempt

if TYPE_CHECKING:
    from sqlalchemy import Result, Select
    from sqlalchemy.ext.asyncio import AsyncSession


class SavingDao:
    @staticmethod
    async def bonus_hash(db: AsyncSession, product_id: str) -> str | None:
        """조회 행이 없으면 SQLAlchemy가 None을 반환하며 신규 상품으로 처리한다."""
        return await db.scalar(select(Saving.bonus_source_hash).where(Saving.product_id == product_id))

    @staticmethod
    async def merge(db: AsyncSession, saving: Saving) -> None:
        await db.merge(saving)

    @staticmethod
    async def create_rate_options(db: AsyncSession, options: Sequence[RateOption]) -> None:
        db.add_all(options)
        await db.flush()

    @staticmethod
    async def delete_rate_options(db: AsyncSession, product_id: str) -> None:
        await db.execute(delete(RateOption).where(RateOption.product_id == product_id))

    @staticmethod
    async def delete_bonuses(db: AsyncSession, product_id: str) -> None:
        await db.execute(delete(SavingBonus).where(SavingBonus.product_id == product_id))

    @staticmethod
    async def create_bonuses(db: AsyncSession, bonuses: Sequence[SavingBonus]) -> None:
        db.add_all(bonuses)
        await db.flush()

    @staticmethod
    async def list_all(db: AsyncSession, limit: int, offset: int = 0) -> Sequence[Saving]:
        query: Select[tuple[Saving]] = (
            select(Saving)
            .options(
                selectinload(Saving.rate_options),
                selectinload(Saving.bonuses),
                selectinload(Saving.condition),
            )
            .order_by(Saving.product_id)
            .limit(limit)
            .offset(offset)
        )
        result: Result[tuple[Saving]] = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def list_every(db: AsyncSession, page_size: int) -> list[Saving]:
        every_saving: list[Saving] = []
        while True:
            page: Sequence[Saving] = await SavingDao.list_all(
                db, limit=page_size, offset=len(every_saving),
            )
            if not page:
                return every_saving

            every_saving.extend(page)

    @staticmethod
    async def merge_condition(db: AsyncSession, condition: SavingCondition) -> None:
        await db.merge(condition)

    @staticmethod
    async def create_condition_attempt(db: AsyncSession, attempt: SavingConditionAttempt) -> None:
        db.add(attempt)
        await db.flush()

    @staticmethod
    async def lock_by_id(db: AsyncSession, product_id: str) -> Saving | None:
        """상품 부재는 None으로 반환해 서비스가 저장을 중단하도록 한다."""
        query: Select[tuple[Saving]] = (
            select(Saving).where(Saving.product_id == product_id)
            .options(selectinload(Saving.rate_options)).with_for_update()
        )
        return await db.scalar(query)
