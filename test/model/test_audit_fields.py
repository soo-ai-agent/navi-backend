from datetime import datetime, timedelta, timezone
from unittest import IsolatedAsyncioTestCase

from sqlalchemy import insert, select, update
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.dao.bank import BankDao
from app.model.database.bank import Bank
from app.model.database.base import Base


class TestAuditFields(IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def asyncTearDown(self) -> None:
        await self.engine.dispose()

    async def seed_bank(self) -> None:
        async with self.sessions.begin() as session:
            session.add(Bank(
                bank_code="test", original_name="은행", display_name="은행",
                created_by="import", updated_by="import",
                created_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
                updated_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
            ))

    async def test_새_행에_시스템_주체와_UTC_시각이_저장된다(self) -> None:
        async with self.sessions.begin() as session:
            bank: Bank = Bank(bank_code="test", original_name="은행", display_name="은행")
            session.add(bank)
            await session.flush()

            self.assertEqual(("system", "system"), (bank.created_by, bank.updated_by))
            self.assertEqual(timezone.utc, bank.created_at.tzinfo)
            self.assertEqual(bank.created_at, bank.updated_at)

    async def test_병합_수정은_생성_이력을_보존하고_수정_이력만_갱신한다(self) -> None:
        await self.seed_bank()

        async with self.sessions.begin() as session:
            await BankDao.merge(session, Bank(
                bank_code="test", original_name="은행", display_name="새 은행",
            ))

        async with self.sessions() as session:
            bank: Bank = (await session.scalars(select(Bank))).one()
            self.assertEqual("import", bank.created_by)
            self.assertEqual(datetime(2020, 1, 1, tzinfo=timezone.utc), bank.created_at)
            self.assertEqual("system", bank.updated_by)
            self.assertGreater(bank.updated_at, bank.created_at)

    async def test_변경_없는_병합은_수정_시각을_바꾸지_않는다(self) -> None:
        await self.seed_bank()

        async with self.sessions.begin() as session:
            await BankDao.merge(session, Bank(bank_code="test", original_name="은행", display_name="은행"))

        async with self.sessions() as session:
            bank: Bank = (await session.scalars(select(Bank))).one()
            self.assertEqual(datetime(2020, 1, 1, tzinfo=timezone.utc), bank.updated_at)
            self.assertEqual("import", bank.updated_by)

    async def test_명시한_수정_주체가_저장된다(self) -> None:
        await self.seed_bank()

        async with self.sessions.begin() as session:
            bank: Bank = (await session.scalars(select(Bank))).one()
            bank.record_change("manual-review")

        async with self.sessions() as session:
            bank = (await session.scalars(select(Bank))).one()
            self.assertEqual("manual-review", bank.updated_by)
            self.assertGreater(bank.updated_at, bank.created_at)

    async def test_빈_수정_주체나_너무_긴_수정_주체는_거절한다(self) -> None:
        bank: Bank = Bank(bank_code="test", original_name="은행", display_name="은행")

        for actor in (" ", "x" * 129):
            with self.subTest(actor=actor), self.assertRaises(ValueError):
                bank.record_change(actor)

    async def test_SQLAlchemy_UPDATE도_수정_시각과_주체를_갱신한다(self) -> None:
        await self.seed_bank()

        async with self.sessions.begin() as session:
            await session.execute(update(Bank).values(display_name="변경"))

        async with self.sessions() as session:
            bank: Bank = (await session.scalars(select(Bank))).one()
            self.assertEqual("system", bank.updated_by)
            self.assertGreater(bank.updated_at, bank.created_at)

    async def test_다른_시간대의_입력은_UTC로_저장한다(self) -> None:
        async with self.sessions.begin() as session:
            session.add(Bank(
                bank_code="test", original_name="은행", display_name="은행",
                created_at=datetime(2020, 1, 1, 9, tzinfo=timezone(timedelta(hours=9))),
            ))

        async with self.sessions() as session:
            bank: Bank = (await session.scalars(select(Bank))).one()
            self.assertEqual(datetime(2020, 1, 1, tzinfo=timezone.utc), bank.created_at)

    async def test_시간대_없는_시각은_저장하지_않는다(self) -> None:
        async with self.sessions() as session:
            session.add(Bank(
                bank_code="test", original_name="은행", display_name="은행",
                created_at=datetime(2020, 1, 1),
            ))

            with self.assertRaises(StatementError):
                await session.flush()

    async def test_감사_컬럼에_NULL을_저장하지_못한다(self) -> None:
        async with self.engine.begin() as connection:
            with self.assertRaises(IntegrityError):
                await connection.execute(insert(Bank).values(
                    bank_code="test", original_name="은행", display_name="은행", created_by=None,
                ))
