from __future__ import annotations

from typing import TYPE_CHECKING

from infra.cache.timed_cache import TimedCache
from infra.request_context import short_request_id

if TYPE_CHECKING:
    from logging import Logger
    from app.model.vo.questions_vo import QuestionsVO
    from app.source.questions_source import QuestionsSource


class QuestionsCache:
    """질문 묶음을 TTL 동안 보관한다. 실제 조회는 감싼 공급자가 한다."""

    _origin: QuestionsSource
    _logger: Logger
    _cache: TimedCache[QuestionsVO]

    def __init__(self, origin: QuestionsSource, logger: Logger) -> None:
        self._origin = origin
        self._logger = logger
        self._cache = TimedCache()

    async def get(self, request_id: str = "background") -> QuestionsVO:
        cached: QuestionsVO | None = self._cache.fresh()
        if cached is not None:
            return cached

        loaded: QuestionsVO = await self._origin.get(request_id)
        self._cache.store(loaded)

        self._logger.debug("질문 캐시 적재 | req=%s | 질문수=%d", short_request_id(request_id), len(loaded.questions))
        return loaded

    def clear(self) -> None:
        self._cache.clear()
