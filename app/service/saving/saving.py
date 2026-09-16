from __future__ import annotations
from typing import TYPE_CHECKING, Sequence
from app.model.database.saving_condition import SavingCondition
from app.model.database.saving_condition_attempt import SavingConditionAttempt
from app.model.vo.saving_condition_source_vo import SavingConditionSourceVO
from app.model.vo.saving_products_vo import SavingProductsVO

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from app.dao.saving import SavingDao
    from app.model.database.saving import Saving
    from app.model.database.saving_bonus import SavingBonus
    from app.model.database.rate_option import RateOption

_LIMIT = 1000
"""한 번에 조회할 상품 수. 수집과 추천 캐시는 마지막 페이지까지 순회한다"""


class SavingService:
    _async_session_maker: async_sessionmaker[AsyncSession]
    _saving_dao: SavingDao

    def __init__(
            self,
            async_session_maker: async_sessionmaker[AsyncSession],
            saving_dao: SavingDao,
    ) -> None:
        self._async_session_maker = async_session_maker
        self._saving_dao = saving_dao

    async def get(self, request_id: str = "background") -> SavingProductsVO:
        return SavingProductsVO(products=tuple(await self.list_every()))

    def clear(self) -> None:
        """보관하는 것이 없어 버릴 것도 없다."""

    async def list_all(self, offset: int = 0) -> Sequence[Saving]:
        async with self._async_session_maker() as session:
            return await self._saving_dao.list_all(session, limit=_LIMIT, offset=offset)

    async def list_every(self) -> list[Saving]:
        async with self._async_session_maker() as session:
            return await self._saving_dao.list_every(session, page_size=_LIMIT)

    async def save_conditions(self, condition: SavingCondition, bonuses: Sequence[SavingBonus]) -> bool:
        async with self._async_session_maker() as session:
            async with session.begin():
                return await self._replace_conditions(session, condition, bonuses)

    async def _replace_conditions(
            self, session: AsyncSession, condition: SavingCondition, bonuses: Sequence[SavingBonus],
    ) -> bool:
        # DAO 조회 부재는 저장 대상이 사라진 경계 상황이므로 여기서만 None 을 검사한다.
        saving: Saving | None = await self._saving_dao.lock_by_id(session, condition.product_id)
        if saving is None:
            return False

        source: SavingConditionSourceVO = saving.condition_source()
        if not condition.matches(source):
            return False

        await self._saving_dao.merge_condition(session, condition)
        await self._saving_dao.delete_bonuses(session, condition.product_id)
        await self._saving_dao.create_bonuses(session, bonuses)
        return True

    async def link_homepage(self, product_id: str, homepage_url: str) -> bool:
        async with self._async_session_maker() as session, session.begin():
            # DAO 조회 부재는 저장 대상이 사라진 경계 상황이므로 여기서만 None 을 검사한다.
            saving: Saving | None = await self._saving_dao.lock_by_id(session, product_id)
            if saving is None:
                return False

            saving.link_homepage(homepage_url)
            return True

    async def save_condition_attempt(self, attempt: SavingConditionAttempt) -> None:
        async with self._async_session_maker() as session, session.begin():
            await self._saving_dao.create_condition_attempt(session, attempt)

    async def invalidate_changed_conditions(self) -> None:
        """
        공시 원문이 바뀐 상품의 조건을 추출 대기로 되돌린다.

        다음 구조화 배치가 이 상품들을 다시 번역한다. 한 트랜잭션으로 처리해 중간에 실패해도
        일부만 되돌아간 상태가 남지 않게 한다.
        """
        every_saving: list[Saving] = await self.list_every()

        async with self._async_session_maker() as session:
            async with session.begin():
                for saving in every_saving:
                    if not self._condition_outdated(saving):
                        continue

                    source: SavingConditionSourceVO = saving.condition_source()
                    await self._replace_conditions(session, SavingCondition.pending(source), ())

    @staticmethod
    def _condition_outdated(saving: Saving) -> bool:
        """저장된 조건이 지금 공시 원문과 어긋나는가. 조건이 아예 없으면 새로 뽑아야 한다."""
        if saving.condition is None:
            return True

        source: SavingConditionSourceVO = saving.condition_source()
        return not saving.condition.matches(source)

    async def save_all(self, products: Sequence[Saving]) -> int:
        async with self._async_session_maker() as session:
            async with session.begin():
                changed: int = 0
                for saving in products:
                    previous_hash: str | None = await self._saving_dao.bonus_hash(session, saving.product_id)
                    await self._saving_dao.merge(session, saving)

                    if not saving.bonus_source_changed_from(previous_hash):
                        continue

                    await self._saving_dao.delete_bonuses(session, saving.product_id)
                    changed += 1

                return changed

    async def replace_rate_options(self, options: Sequence[RateOption], saving_ids: Sequence[str]) -> int:
        replaced_saving_ids: set[str] = set(saving_ids)
        for option in options:
            replaced_saving_ids.add(option.product_id)

        async with self._async_session_maker() as session:
            async with session.begin():
                for product_id in replaced_saving_ids:
                    await self._saving_dao.delete_rate_options(session, product_id)

                await self._saving_dao.create_rate_options(session, options)

        return len(options)
