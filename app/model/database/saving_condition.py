from __future__ import annotations
from sqlalchemy import Enum as SAEnum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.enums.saving_condition import ConditionStatus
from app.constants.saving_condition import CONDITION_SCHEMA_VERSION
from app.model.database.base import Base
from app.model.vo.extracted_conditions_vo import ExtractedConditionsVO
from app.model.vo.saving_condition_source_vo import SavingConditionSourceVO


class SavingCondition(Base):
    __tablename__ = "product_condition"

    product_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("product.product_id"), primary_key=True, comment="상품 식별자"
    )
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False, comment="조건 추출 입력 해시")
    schema_version: Mapped[str] = mapped_column(String(16), nullable=False, comment="추출 규칙 버전")
    status: Mapped[ConditionStatus] = mapped_column(
        SAEnum(ConditionStatus, native_enum=False), nullable=False, comment="추출·확인 필요·실패"
    )
    source_json: Mapped[str] = mapped_column(Text, nullable=False, comment="추출 당시 입력과 정형 조건")
    conditions_json: Mapped[str] = mapped_column(Text, nullable=False, comment="검증된 필수·우대조건 JSON")
    review_reason: Mapped[str] = mapped_column(Text, nullable=False, comment="확인 필요 사유")

    def matches(self, source: SavingConditionSourceVO) -> bool:
        return self.source_hash == source.source_hash() and self.schema_version == CONDITION_SCHEMA_VERSION

    @classmethod
    def pending(cls, source: SavingConditionSourceVO) -> SavingCondition:
        return cls.record(source, ConditionStatus.PENDING, "", "추출 대기")

    def can_skip(self, source: SavingConditionSourceVO) -> bool:
        return self.matches(source) and self.status in (
            ConditionStatus.EXTRACTED, ConditionStatus.NEEDS_REVIEW
        )

    @classmethod
    def record(
            cls, source: SavingConditionSourceVO, status: ConditionStatus, conditions_json: str, reason: str
    ) -> SavingCondition:
        return cls(
            product_id=source.product_id, source_hash=source.source_hash(),
            schema_version=CONDITION_SCHEMA_VERSION, status=status,
            source_json=source.model_dump_json(), conditions_json=conditions_json, review_reason=reason,
        )

    @classmethod
    def from_extracted(cls, source: SavingConditionSourceVO, extracted: ExtractedConditionsVO) -> SavingCondition:
        extracted.verify(source)
        if extracted.needs_review(source):
            return cls.from_checklist(source, "AI 응답에 미해석 조건 또는 정보 부족이 남아 공시 원문 체크리스트로 저장했습니다.")
        return cls.record(source, ConditionStatus.EXTRACTED, extracted.model_dump_json(), "")

    @classmethod
    def from_checklist(cls, source: SavingConditionSourceVO, reason: str) -> SavingCondition:
        extracted: ExtractedConditionsVO = ExtractedConditionsVO.from_source_checklist(source)
        extracted.verify(source)
        status: ConditionStatus = ConditionStatus.EXTRACTED
        if extracted.needs_review(source):
            status = ConditionStatus.NEEDS_REVIEW
        return cls.record(source, status, extracted.model_dump_json(), reason)

    @classmethod
    def from_manual(cls, source: SavingConditionSourceVO, extracted: ExtractedConditionsVO) -> SavingCondition:
        extracted.verify(source)
        if extracted.needs_review(source):
            raise ValueError("직접 작성한 조건에도 미해석 항목 또는 공시 정보 부족이 남아 있습니다")
        return cls.record(
            source, ConditionStatus.EXTRACTED, extracted.model_dump_json(),
            "공시 원문 기반 직접 작성(Codex). 외부 LLM 호출 없음. 미판정 항목은 체크리스트로 보존.",
        )

    def read_verified(self, source: SavingConditionSourceVO) -> ExtractedConditionsVO | ConditionStatus:
        if not self.matches(source):
            return ConditionStatus.PENDING

        if self.status is not ConditionStatus.EXTRACTED:
            return self.status

        try:
            extracted: ExtractedConditionsVO = ExtractedConditionsVO.model_validate_json(self.conditions_json)
            extracted.verify(source)
        except ValueError:
            # 저장 당시에는 통과했어도 검증 규칙이 바뀌었을 수 있다. 판정에 쓰지 않고 실패로 알린다.
            return ConditionStatus.FAILED

        if extracted.needs_review(source):
            return ConditionStatus.NEEDS_REVIEW

        return extracted
