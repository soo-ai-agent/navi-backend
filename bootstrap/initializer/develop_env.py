from __future__ import annotations

from typing import TYPE_CHECKING

from app.model.database.base import Base
from bootstrap.initializer.audit_columns import add_audit_columns

if TYPE_CHECKING:
    from bootstrap.container.application import ApplicationConfig


class DevelopEnvDbInitializer:
    """개발·배치 실행 때 테이블을 만든다. 운영은 DEV 가 꺼져 있어 아무것도 하지 않는다."""

    def __init__(self, di_container: ApplicationConfig) -> None:
        self._di_container = di_container

    async def __call__(self, force_init: bool = False) -> None:
        context = self._di_container.context()
        if not context.app_config.DEV and not force_init:
            return

        context.logger.info("Initializing database...")
        async with self._di_container.component.async_sqlalchemy_engine().begin() as conn:
            if conn.dialect.name == "sqlite":
                # 워커들이 테이블 존재 확인과 생성을 동시에 수행하지 않도록 SQLite 쓰기 잠금을 먼저 잡는다.
                await conn.exec_driver_sql("BEGIN IMMEDIATE")
            await conn.run_sync(Base.metadata.create_all)
            if conn.dialect.name == "sqlite":
                await conn.run_sync(add_audit_columns)
        context.logger.info("Successfully initialized database.")
