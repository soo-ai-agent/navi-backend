from __future__ import annotations
import os
import sqlite3
from asyncio import to_thread
from datetime import datetime

_SQLITE_URL_PREFIX: str = "sqlite+aiosqlite:///"


class SqliteBackup:
    """
    sqlite DB 파일을 백업 디렉터리에 복사한다.

    열려 있는 DB 에서도 일관된 복사본이 나오도록 sqlite3 백업 API 를 쓴다
    (shutil.copy 는 쓰기 도중이면 깨진 복사본이 될 수 있다).
    """

    _database_url: str
    _backup_dir: str

    def __init__(self, database_url: str, backup_dir: str) -> None:
        self._database_url = database_url
        self._backup_dir = backup_dir

    async def create(self) -> str:
        """백업 파일을 만들고 그 경로를 돌려준다. 실패하면 예외를 그대로 올린다."""
        return await to_thread(self._copy)

    def _copy(self) -> str:
        if not self._database_url.startswith(_SQLITE_URL_PREFIX):
            raise ValueError(f"sqlite DB 가 아니라 백업할 수 없습니다: {self._database_url}")

        db_path: str = self._database_url.removeprefix(_SQLITE_URL_PREFIX)
        if not os.path.isfile(db_path):
            raise FileNotFoundError(f"백업할 DB 파일이 없습니다: {db_path}")

        os.makedirs(self._backup_dir, exist_ok=True)
        backup_path: str = os.path.join(self._backup_dir, f"backend-{datetime.now():%Y%m%d-%H%M%S}.db")

        source: sqlite3.Connection = sqlite3.connect(db_path)
        try:
            target: sqlite3.Connection = sqlite3.connect(backup_path)
            try:
                source.backup(target)
            finally:
                target.close()
        finally:
            source.close()
        return backup_path
