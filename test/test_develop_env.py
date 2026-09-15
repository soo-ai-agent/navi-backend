from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from logging import getLogger
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import IsolatedAsyncioTestCase

from sqlalchemy import inspect, insert, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.model.database.bank import Bank
from app.model.database.base import Base
from bootstrap.config_base import AppConfig
from bootstrap.container.application import ApplicationConfig
from bootstrap.context import Context
from bootstrap.initializer.develop_env import DevelopEnvDbInitializer


async def initialize(database_url: str, *, development: bool = True) -> None:
    container = ApplicationConfig()
    settings = AppConfig(DATABASE_URL=database_url, DEV=development)
    Context(container, getLogger("test.initializer"), settings)
    engine = container.component.async_sqlalchemy_engine()
    try:
        await DevelopEnvDbInitializer(container)()
    finally:
        await engine.dispose()


class TestDevelopEnvInitializer(IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.directory = TemporaryDirectory()
        database = Path(self.directory.name) / "startup.db"
        self.database_url = f"sqlite+aiosqlite:///{database}"
        self.engine = create_async_engine(self.database_url)

    async def asyncTearDown(self) -> None:
        await self.engine.dispose()
        self.directory.cleanup()

    async def create_legacy_bank(self) -> None:
        async with self.engine.begin() as connection:
            await connection.exec_driver_sql(
                "CREATE TABLE bank (bank_code VARCHAR(16) PRIMARY KEY, "
                "original_name VARCHAR(64) NOT NULL, display_name VARCHAR(64) NOT NULL, "
                "homepage_url VARCHAR(255) NOT NULL, call_center VARCHAR(64) NOT NULL)"
            )
            await connection.exec_driver_sql(
                "INSERT INTO bank VALUES ('legacy', '기존 은행', '기존 은행', '', '')"
            )

    async def test_기존_행은_데이터를_보존하고_이관_시각을_기록한다(self) -> None:
        await self.create_legacy_bank()
        started_at: datetime = datetime.now(timezone.utc).replace(microsecond=0)

        await initialize(self.database_url)

        async with async_sessionmaker(self.engine)() as session:
            bank = (await session.scalars(select(Bank).where(Bank.bank_code == "legacy"))).one()
            self.assertEqual("기존 은행", bank.display_name)
            self.assertEqual(("migration", "migration"), (bank.created_by, bank.updated_by))
            self.assertGreaterEqual(bank.created_at, started_at)
            self.assertEqual(bank.created_at, bank.updated_at)

    async def test_마이그레이션을_다시_실행해도_이관_이력이_유지된다(self) -> None:
        await self.create_legacy_bank()
        await initialize(self.database_url)
        async with self.engine.connect() as connection:
            original = (await connection.execute(select(
                Bank.created_by, Bank.created_at, Bank.updated_by, Bank.updated_at,
            ))).one()

        await initialize(self.database_url)

        async with self.engine.connect() as connection:
            repeated = (await connection.execute(select(
                Bank.created_by, Bank.created_at, Bank.updated_by, Bank.updated_at,
            ))).one()
        self.assertEqual(original, repeated)

    async def test_이관한_테이블의_새_행은_이관_시각을_재사용하지_않는다(self) -> None:
        await self.create_legacy_bank()
        async with self.engine.begin() as connection:
            await connection.exec_driver_sql(
                "ALTER TABLE bank ADD COLUMN created_at DATETIME NOT NULL DEFAULT '2020-01-01 00:00:00'"
            )
            await connection.exec_driver_sql(
                "ALTER TABLE bank ADD COLUMN updated_at DATETIME NOT NULL DEFAULT '2020-01-01 00:00:00'"
            )
        await initialize(self.database_url)
        started_at: datetime = datetime.now(timezone.utc).replace(microsecond=0)
        async with self.engine.begin() as connection:
            await connection.execute(insert(Bank).values(
                bank_code="new", original_name="새 은행", display_name="새 은행",
            ))

        async with async_sessionmaker(self.engine)() as session:
            bank = (await session.scalars(select(Bank).where(Bank.bank_code == "new"))).one()
            self.assertGreaterEqual(bank.created_at, started_at)
            self.assertGreaterEqual(bank.updated_at, started_at)

    async def test_여덟_워커가_동시에_이관해도_중복_컬럼_오류가_없다(self) -> None:
        await self.create_legacy_bank()

        await asyncio.gather(*(initialize(self.database_url) for _ in range(8)))

        async with async_sessionmaker(self.engine)() as session:
            bank = (await session.scalars(select(Bank).where(Bank.bank_code == "legacy"))).one()
            self.assertEqual("migration", bank.created_by)

    async def test_여덟_워커가_동시에_초기화해도_모든_테이블을_생성한다(self) -> None:
        await asyncio.gather(*(initialize(self.database_url) for _ in range(8)))

        async with self.engine.connect() as connection:
            tables = await connection.run_sync(lambda sync: inspect(sync).get_table_names())
        self.assertEqual(set(Base.metadata.tables), set(tables))

    async def test_재초기화해도_기존_데이터를_보존한다(self) -> None:
        await initialize(self.database_url)
        async with self.engine.begin() as connection:
            await connection.execute(insert(Bank).values(
                bank_code="test", original_name="테스트 은행", display_name="테스트 은행",
            ))

        await initialize(self.database_url)

        async with self.engine.connect() as connection:
            name = await connection.scalar(select(Bank.display_name).where(Bank.bank_code == "test"))
        self.assertEqual("테스트 은행", name)

    async def test_개발모드가_아니면_테이블을_생성하지_않는다(self) -> None:
        await initialize(self.database_url, development=False)

        async with self.engine.connect() as connection:
            tables = await connection.run_sync(lambda sync: inspect(sync).get_table_names())
        self.assertEqual([], tables)
