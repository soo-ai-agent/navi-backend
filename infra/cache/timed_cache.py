from __future__ import annotations
import time
from typing import Generic, TypeVar

_TTL_SECONDS = 600
T = TypeVar("T")


class TimedCache(Generic[T]):
    """
    적재 배치는 별도 프로세스라 이 캐시를 직접 비울 수 없고, 웹 워커도 여러 개다.
    그래서 만료로 갱신한다 — 공시는 한 달에 한 번 바뀌므로 10분이면 충분하다.

    ponytail: 프로세스별 메모리 캐시. 워커마다 따로 들고 있어 갱신 시점이 최대 TTL 만큼
    어긋난다. 즉시 반영이 필요해지면 Redis 같은 공유 저장소로 옮긴다.
    """

    _cached: T | None  # 아직 조회하지 않은 상태를 조회 결과가 빈 경우와 구분한다.
    _cached_at: float

    def __init__(self) -> None:
        self._cached = None
        self._cached_at = 0.0

    def fresh(self) -> T | None:
        if self._cached is None:
            return None

        if time.monotonic() - self._cached_at >= _TTL_SECONDS:
            return None

        return self._cached

    def store(self, value: T) -> None:
        self._cached = value
        self._cached_at = time.monotonic()

    def clear(self) -> None:
        self._cached = None
        self._cached_at = 0.0
