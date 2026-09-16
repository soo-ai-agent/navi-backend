from __future__ import annotations
import asyncio
import json
from pathlib import Path
from typing import Mapping, Sequence
from infra.request_context import current_request_id, short_request_id
from app.model.database.saving import Saving
from bootstrap.container.application import ApplicationConfig
from bootstrap.context import Context
from config import app_config, logger as _logger

HOMEPAGE_FILE = Path("data/product-homepage.json")


async def main() -> None:
    """상품별 은행 안내 페이지 주소를 적재한다.

    공시가 상품 URL을 주지 않아 사람이 직접 채운다. 목록에 없는 상품은 그대로 두고,
    화면은 비어 있는 상품을 은행 대표 홈페이지로 보낸다.
    """
    homepages: Mapping[str, str] = json.loads(HOMEPAGE_FILE.read_text(encoding="utf-8"))

    di_container = ApplicationConfig()
    Context(di_container, _logger, app_config=app_config)
    saving_service = di_container.store.saving_service()

    applied: int = 0
    try:
        offset: int = 0
        while True:
            products: Sequence[Saving] = await saving_service.list_all(offset)
            if not products:
                break
            offset += len(products)
            for saving in products:
                url: str = homepages.get(saving.product_id, "")
                if url == "" or saving.homepage_url == url:
                    continue
                if not await saving_service.link_homepage(saving.product_id, url):
                    _logger.warning("상품 홈페이지 저장 실패 | req=%s | product_id=%s", short_request_id(), saving.product_id)
                    continue
                applied += 1
                _logger.info("상품 홈페이지 저장 | req=%s | product_id=%s", short_request_id(), saving.product_id)
    finally:
        await di_container.component.async_sqlalchemy_engine().dispose()

    print(json.dumps({"적용_상품": applied, "정의_상품": len(homepages)}, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
