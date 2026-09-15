from __future__ import annotations

from typing import Protocol

from app.model.vo.banks_vo import BanksVO


class BanksSource(Protocol):
    async def get(self, request_id: str = "background") -> BanksVO: ...

    def clear(self) -> None: ...
