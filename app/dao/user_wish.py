from __future__ import annotations

from typing import TYPE_CHECKING

from app.model.database.user_wish import UserWish

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class UserWishDao:
    @staticmethod
    async def save(db: AsyncSession, wish: UserWish) -> None:
        db.add(wish)
