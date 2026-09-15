"""
금감원 공시를 적재하고 필수·우대조건을 추출한다.

    python -m scripts.sync_disclosure

상품별 추출 실패는 기록하고 다음 상품을 계속 처리한다.
"""
from __future__ import annotations

import asyncio

from bootstrap.container.application import ApplicationConfig
from bootstrap.context import Context
from bootstrap.initializer import DevelopEnvDbInitializer
from config import app_config, logger as _logger


async def main() -> None:
    di_container = ApplicationConfig()
    Context(di_container, _logger, app_config=app_config)

    await DevelopEnvDbInitializer(di_container)(force_init=True)
    try:
        await di_container.service.saving_refresh_service().refresh()
    finally:
        await di_container.component.async_sqlalchemy_engine().dispose()


if __name__ == '__main__':
    asyncio.run(main())
