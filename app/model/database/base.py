from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.model.database.utc_datetime import UTCDateTime


SYSTEM_ACTOR: str = "system"


class Base(DeclarativeBase):
    created_by: Mapped[str] = mapped_column(
        String(128), nullable=False, default=SYSTEM_ACTOR, server_default=SYSTEM_ACTOR,
        comment="최초 저장 주체. 인증된 사용자가 없는 수집 작업은 system",
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=func.now(), server_default=func.now(),
        comment="최초 저장 시각(UTC). 기존 행의 migration 생성자는 이관 기준 시각",
    )
    updated_by: Mapped[str] = mapped_column(
        String(128), nullable=False, default=SYSTEM_ACTOR, server_default=SYSTEM_ACTOR,
        onupdate=SYSTEM_ACTOR, comment="마지막 수정 주체",
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=func.now(), server_default=func.now(),
        onupdate=func.now(), comment="마지막 수정 시각(UTC)",
    )

    def record_change(self, actor: str) -> None:
        if not actor.strip() or len(actor) > 128:
            raise ValueError("수정 주체는 공백이 아닌 128자 이내의 식별자여야 합니다")
        self.updated_by = actor
        self.updated_at = datetime.now(timezone.utc).replace(microsecond=0)
