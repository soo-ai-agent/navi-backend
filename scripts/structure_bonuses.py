from __future__ import annotations
import asyncio
from bootstrap.container.application import ApplicationConfig
from bootstrap.context import Context
from bootstrap.initializer import DevelopEnvDbInitializer
from config import app_config, logger as _logger


async def main() -> None:
    """
    저장된 상품의 필수·우대조건을 구조화한다. 실패 상품의 재시도에도 사용한다.

    원문과 추출 버전이 같은 완료·확인 필요 상품은 건너뛴다.
    """
    di_container = ApplicationConfig()
    Context(di_container, _logger, app_config=app_config)

    await DevelopEnvDbInitializer(di_container)(force_init=True)
    try:
        await di_container.service.bonus_structure_service().structure()
    finally:
        await di_container.component.async_sqlalchemy_engine().dispose()


if __name__ == '__main__':
    asyncio.run(main())
