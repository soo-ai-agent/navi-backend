from __future__ import annotations
from typing import Protocol
from app.model.vo.saving_products_vo import SavingProductsVO


class SavingProductsSource(Protocol):
    """
    상품 묶음을 공급하는 창구. 캐시로 받을지 매번 DB 에서 받을지는 컨테이너가 고른다.

    무효화는 공급자마다 뜻이 다르다 — 캐시는 보관분을 버리고, 직접 조회는 할 일이 없다.
    """

    async def get(self, request_id: str = "background") -> SavingProductsVO: ...

    def clear(self) -> None: ...
