from __future__ import annotations

from typing import ClassVar, TYPE_CHECKING

from dependency_injector import containers, providers
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncEngine, AsyncSession, create_async_engine

from infra.sqlite_backup import SqliteBackup

if TYPE_CHECKING:
    from bootstrap.context import Context
    from bootstrap.config_base import AppConfig


def _create_engine(app_config: AppConfig) -> AsyncEngine:
    if app_config.DATABASE_URL.startswith("sqlite+aiosqlite:///"):
        # SQLAlchemy는 DB 드라이버 인자를 dict로 받는다.
        return create_async_engine(
            app_config.DATABASE_URL, connect_args={"check_same_thread": False}
        )
    return create_async_engine(
        app_config.DATABASE_URL, pool_pre_ping=True, pool_recycle=3600
    )


class ComponentConfig(containers.DeclarativeContainer):
    context: ClassVar[providers.Provider[Context[AppConfig]]] = providers.Provider()

    async_sqlalchemy_engine: ClassVar[providers.Provider[AsyncEngine]] = providers.Singleton(
        _create_engine,
        app_config=context.provided.app_config
    )
    async_session_maker: ClassVar[providers.Provider[async_sessionmaker[AsyncSession]]] = providers.Singleton(
        async_sessionmaker, async_sqlalchemy_engine
    )
    db_backup: ClassVar[providers.Provider[SqliteBackup]] = providers.Singleton(
        SqliteBackup,
        database_url=context.provided.app_config.DATABASE_URL,
        backup_dir=context.provided.app_config.BACKUP_DIR,
    )
