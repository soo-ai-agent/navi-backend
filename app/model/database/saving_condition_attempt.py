from __future__ import annotations
from sqlalchemy import Enum as SAEnum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.enums.saving_condition import ConditionAttemptStatus
from app.model.database.base import Base
from app.model.vo.saving_condition_source_vo import SavingConditionSourceVO


class SavingConditionAttempt(Base):
    __tablename__ = "product_condition_attempt"
    __table_args__ = {"comment": "조건 추출 시도의 원문과 결과. 추천 판정에는 사용하지 않는다"}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    product_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("product.product_id"), nullable=False, index=True
    )
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_json: Mapped[str] = mapped_column(Text, nullable=False)
    raw_response: Mapped[str] = mapped_column(
        Text, nullable=False, comment="LLM 응답 원문. 검증 전 값을 그대로 보관한다"
    )
    status: Mapped[ConditionAttemptStatus] = mapped_column(
        SAEnum(ConditionAttemptStatus, native_enum=False), nullable=False
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")

    @classmethod
    def validated(cls, source: SavingConditionSourceVO, raw_response: str) -> SavingConditionAttempt:
        return cls.record(source, raw_response, ConditionAttemptStatus.VALIDATED, "")

    @classmethod
    def failed(
            cls, source: SavingConditionSourceVO, raw_response: str, reason: str
    ) -> SavingConditionAttempt:
        return cls.record(source, raw_response, ConditionAttemptStatus.FAILED, reason)

    @classmethod
    def record(
            cls,
            source: SavingConditionSourceVO,
            raw_response: str,
            status: ConditionAttemptStatus,
            reason: str,
    ) -> SavingConditionAttempt:
        return cls(
            product_id=source.product_id,
            source_hash=source.source_hash(),
            source_json=source.model_dump_json(),
            raw_response=raw_response,
            status=status,
            reason=reason,
        )
