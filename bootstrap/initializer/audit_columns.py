from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.engine import Connection

from app.model.database.base import Base


def add_audit_columns(connection: Connection) -> None:
    migrated_at: str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    for table in Base.metadata.sorted_tables:
        table_name: str = connection.dialect.identifier_preparer.quote(table.name)
        column_names: set[str] = set(connection.exec_driver_sql(
            f"PRAGMA table_info({table_name})"
        ).scalars(index=1))
        if "created_by" not in column_names:
            connection.exec_driver_sql(
                f"ALTER TABLE {table_name} ADD COLUMN created_by VARCHAR(128) NOT NULL DEFAULT 'system'"
            )
            connection.exec_driver_sql(f"UPDATE {table_name} SET created_by = 'migration'")
        if "created_at" not in column_names:
            # SQLite ADD COLUMN은 CURRENT_TIMESTAMP를 기본값으로 허용하지 않는다.
            # 기존 행의 실제 생성 시각은 알 수 없으며 새 ORM INSERT는 Base의 default가 현재 시각을 넣는다.
            connection.exec_driver_sql(
                f"ALTER TABLE {table_name} ADD COLUMN created_at DATETIME NOT NULL DEFAULT '{migrated_at}'"
            )
        if "updated_by" not in column_names:
            connection.exec_driver_sql(
                f"ALTER TABLE {table_name} ADD COLUMN updated_by VARCHAR(128) NOT NULL DEFAULT 'system'"
            )
            connection.exec_driver_sql(f"UPDATE {table_name} SET updated_by = 'migration'")
        if "updated_at" not in column_names:
            connection.exec_driver_sql(
                f"ALTER TABLE {table_name} ADD COLUMN updated_at DATETIME NOT NULL DEFAULT '{migrated_at}'"
            )
