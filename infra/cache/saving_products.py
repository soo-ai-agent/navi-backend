from __future__ import annotations

from typing import TYPE_CHECKING

from infra.cache.timed_cache import TimedCache
from infra.request_context import short_request_id

if TYPE_CHECKING:
    from logging import Logger
    from app.model.vo.saving_products_vo import SavingProductsVO
    from app.source.saving_products_source import SavingProductsSource


class SavingProductsCache:
    """상품 묶음을 TTL 동안 보관한다. 실제 조회는 감싼 공급자가 한다."""

    _origin: SavingProductsSource
    _logger: Logger
    _cache: TimedCache[SavingProductsVO]

    def __init__(self, origin: SavingProductsSource, logger: Logger) -> None:
        self._origin = origin
        self._logger = logger
        self._cache = TimedCache()

    async def get(self, request_id: str = "background") -> SavingProductsVO:
        cached: SavingProductsVO | None = self._cache.fresh()
        if cached is not None:
            return cached

        loaded: SavingProductsVO = await self._origin.get(request_id)
        self._cache.store(loaded)

        self._logger.debug("상품 캐시 적재 | req=%s | 상품수=%d", short_request_id(request_id), len(loaded.products))
        return loaded

    def clear(self) -> None:
        self._cache.clear()
