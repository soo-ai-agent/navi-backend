from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from app.dao.user_wish import UserWishDao
    from app.model.database.user_wish import UserWish


class WishService:
    _async_session_maker: async_sessionmaker[AsyncSession]
    _user_wish_dao: UserWishDao

    def __init__(
            self,
            async_session_maker: async_sessionmaker[AsyncSession],
            user_wish_dao: UserWishDao,
    ) -> None:
        self._async_session_maker = async_session_maker
        self._user_wish_dao = user_wish_dao

    async def save(self, wish: UserWish) -> int:
        async with self._async_session_maker() as session:
            async with session.begin():
                await self._user_wish_dao.save(session, wish)
                # 세션 밖에서 만료된 속성을 읽지 않도록 커밋 전에 채번된 id 를 확보한다.
                await session.flush()
                wish_id: int = wish.id
            return wish_id
