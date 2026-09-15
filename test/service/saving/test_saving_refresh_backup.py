import logging
import os
import sqlite3
import tempfile
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock

from app.dto.response.saving_refresh import BonusStructureResponseDTO, DisclosureSyncResponseDTO
from app.exception.saving import SavingBackupError
from app.service.saving.saving_refresh import SavingRefreshService
from infra.sqlite_backup import SqliteBackup


def _make_service(db_backup: SqliteBackup) -> tuple[SavingRefreshService, AsyncMock, AsyncMock]:
    disclosure_sync = AsyncMock()
    disclosure_sync.sync.return_value = DisclosureSyncResponseDTO(
        banks=1, products=1, rate_options=1, bonus_reset_savings=0,
    )
    bonus_structure = AsyncMock()
    bonus_structure.structure.return_value = BonusStructureResponseDTO(
        scanned_savings=1, structured_savings=0, created_bonuses=0,
        not_structurable_savings=0, skipped_savings=1,
    )
    service = SavingRefreshService(
        disclosure_sync_service=disclosure_sync,
        bonus_structure_service=bonus_structure,
        savings_source=MagicMock(),
        bank_service=MagicMock(),
        questions_service=MagicMock(),
        db_backup=db_backup,
        logger=logging.getLogger("test.refresh"),
    )
    return service, disclosure_sync, bonus_structure


class TestSavingRefreshBackup(IsolatedAsyncioTestCase):
    async def test_refresh_creates_backup_file_before_work(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "backend.db")
            sqlite3.connect(db_path).execute("create table t (id integer)").connection.commit()
            backup_dir = os.path.join(tmp, "backups")
            backup = SqliteBackup(f"sqlite+aiosqlite:///{db_path}", backup_dir)
            service, disclosure_sync, bonus_structure = _make_service(backup)

            await service.refresh()

            backups = os.listdir(backup_dir)
            self.assertEqual(1, len(backups))
            self.assertRegex(backups[0], r"^backend-\d{8}-\d{6}\.db$")
            copied = sqlite3.connect(os.path.join(backup_dir, backups[0]))
            self.assertEqual(1, len(copied.execute(
                "select name from sqlite_master where name='t'"
            ).fetchall()))
            disclosure_sync.sync.assert_awaited_once()
            bonus_structure.structure.assert_awaited_once()

    async def test_refresh_stops_when_backup_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            backup = SqliteBackup(
                f"sqlite+aiosqlite:///{os.path.join(tmp, 'missing.db')}", os.path.join(tmp, "backups")
            )
            service, disclosure_sync, bonus_structure = _make_service(backup)

            with self.assertRaises(SavingBackupError):
                await service.refresh()

            disclosure_sync.sync.assert_not_awaited()
            bonus_structure.structure.assert_not_awaited()
