from __future__ import annotations
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING
from sqlalchemy import Date, Enum as SAEnum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.enums.saving import JoinRestriction
from app.enums.saving_condition import ConditionStatus
from app.model.database.base import Base

if TYPE_CHECKING:
    from app.model.database.saving_bonus import SavingBonus
    from app.model.database.saving_condition import SavingCondition
    from app.model.vo.extracted_conditions_vo import ExtractedConditionsVO
    from app.model.vo.saving_condition_source_vo import SavingConditionSourceVO
    from app.model.vo.condition_context_vo import ConditionContextVO
    from app.model.database.rate_option import RateOption


_UNDETAILED_FAILURE_PREFIX = "LLM 호출 또는 조건 검증 실패:"
"""상세 원인 없이 저장된 실패 사유의 머리말. 이 사유는 사용자에게 그대로 보여 주지 않는다"""


class Saving(Base):
    """
    적금 상품 하나. 공시 한 건을 정제한 결과다.

    공시 필드와의 대응 관계는 disclosure.SavingProduct.to_product() 가 정본이다.
    """

    __tablename__ = "product"
    # SQLAlchemy가 테이블 옵션을 dict 형식으로 요구한다.
    __table_args__ = {"comment": "적금 상품. 매달 공시를 받아 갱신한다"}

    product_id: Mapped[str] = mapped_column(String(64), primary_key=True, comment="은행코드:상품코드 — 공시는 이 둘의 복합키로 상품을 구분한다")
    bank_code: Mapped[str] = mapped_column(String(16), ForeignKey("bank.bank_code"), nullable=False, index=True, comment="은행 코드")
    name: Mapped[str] = mapped_column(String(255), nullable=False, comment="상품명")
    join_ways: Mapped[str] = mapped_column(String(255), nullable=False, default='', comment="가입 방법 원문 (영업점,인터넷,스마트폰)")
    join_member: Mapped[str] = mapped_column(String(255), nullable=False, default='', comment="가입 대상 원문")

    join_restriction: Mapped[JoinRestriction] = mapped_column(
        SAEnum(JoinRestriction, native_enum=False), nullable=False,
        comment="가입 제한 — 제한없음·서민전용·일부제한"
    )
    monthly_limit: Mapped[int | None] = mapped_column(
        nullable=True, comment="월 납입 최고 한도(원). 한도 없는 상품은 null"
    )
    bonus_condition_text: Mapped[str] = mapped_column(
        Text, nullable=False, default='',
        comment="우대조건 원문. 판정 근거를 사용자·검수자에게 보여주기 위해 버리지 않는다"
    )
    bonus_source_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, default='',
        comment="우대조건 원문의 해시. 원문이 그대로면 AI 재번역과 재검수를 건너뛴다"
    )
    after_maturity_rate_text: Mapped[str] = mapped_column(
        Text, nullable=False, default='', comment="만기 후 이자율 원문"
    )
    etc_note: Mapped[str] = mapped_column(
        Text, nullable=False, default='', comment="유의사항 원문"
    )
    disclosure_month: Mapped[str] = mapped_column(
        String(7), nullable=False, comment="공시월 (2026-08 형태)"
    )
    disclosure_start_date: Mapped[date] = mapped_column(
        Date, nullable=False, comment="공시 시작일"
    )
    homepage_url: Mapped[str] = mapped_column(
        Text, nullable=False, default='',
        comment="은행 사이트의 이 상품 안내 페이지. 공시가 주지 않아 직접 채우며, 비어 있으면 은행 대표 홈으로 보낸다"
    )

    rate_options: Mapped[list[RateOption]] = relationship(
        back_populates="saving", cascade="all, delete-orphan"
    )
    """기간·적립방식별 금리. 매달 통째로 갈아끼우므로 상품이 지워지면 함께 지운다"""

    bonuses: Mapped[list[SavingBonus]] = relationship(
        back_populates="saving", cascade="all, delete-orphan"
    )
    """기존 형식을 위한 호환 우대조건. 추천 판정은 condition의 전체 조건을 읽는다"""

    # 아직 추출하지 않은 상품은 조건 행이 없으므로 None 이 필요하다.
    condition: Mapped[SavingCondition | None] = relationship(cascade="all, delete-orphan", single_parent=True)
    """AI 가 추출한 필수·우대조건. 추천 판정이 읽는 원본이다"""

    ID_SEPARATOR = ":"
    """product_id 는 은행코드와 상품코드를 이 문자로 이은 값이다"""

    def bonus_source_changed_from(self, previous_hash: str | None) -> bool:
        """
        우대조건 원문이 지난 적재 때와 달라졌는가.

        그대로면 사람이 검수한 결과를 유지한다 — 매달 같은 검수를 되풀이하지 않는다.
        처음 보는 상품(previous_hash 가 None)은 바뀐 것으로 본다.
        """
        return previous_hash != self.bonus_source_hash

    @classmethod
    def id_of(cls, bank_code: str, saving_code: str) -> str:
        return f"{bank_code}{cls.ID_SEPARATOR}{saving_code}"

    def verified_conditions(self) -> ExtractedConditionsVO | ConditionStatus:
        if self.condition is None:
            return ConditionStatus.PENDING
        source: SavingConditionSourceVO = self.condition_source()
        return self.condition.read_verified(source)

    def condition_unavailable_reason(self, status: ConditionStatus) -> str:
        if status is ConditionStatus.PENDING:
            return "AI 상품 조건 추출이 아직 완료되지 않았습니다."

        if status is ConditionStatus.NEEDS_REVIEW:
            return "AI가 해석하지 못한 조건이나 공시 정보 부족으로 관리자 검토가 필요합니다."

        return self._extraction_failure_reason()

    def _extraction_failure_reason(self) -> str:
        if self.condition is None or self.condition.status is not ConditionStatus.FAILED:
            return "저장된 AI 추출 결과가 검증을 통과하지 못했습니다."

        if self.condition.review_reason.startswith(_UNDETAILED_FAILURE_PREFIX):
            return "이전 AI 조건 추출이 실패했습니다. 상세 원인이 기록되지 않아 관리자 확인이 필요합니다."

        return self.condition.review_reason

    def link_homepage(self, homepage_url: str) -> None:
        """사람이 확인한 은행 안내 페이지를 이 상품에 연결한다. 공시는 이 주소를 주지 않는다."""
        self.homepage_url = homepage_url

    def condition_source(self) -> SavingConditionSourceVO:
        # 순환 참조를 피하려고 함수 안에서 읽는다 — VO 가 이 Entity 를 참조한다.
        from app.model.vo.saving_condition_source_vo import SavingConditionSourceVO

        saving_terms: set[int] = set()
        bonus_points: list[Decimal] = []
        for option in self.rate_options:
            saving_terms.add(option.saving_term_months)

            bonus_point: Decimal = option.max_rate - option.base_rate
            bonus_points.append(bonus_point)

        return SavingConditionSourceVO(
            product_id=self.product_id, name=self.name,
            join_member=self.join_member, join_restriction=self.join_restriction,
            join_ways=self.join_ways, spcl_cnd=self.bonus_condition_text,
            etc_note=self.etc_note, monthly_limit=self.monthly_limit,
            saving_terms=tuple(sorted(saving_terms)), max_bonus_point=max(bonus_points, default=Decimal(0)),
        )

    def condition_context(self, option: RateOption) -> ConditionContextVO:
        # 순환 참조를 피하려고 함수 안에서 읽는다 — VO 가 이 Entity 를 참조한다.
        from app.model.vo.condition_context_vo import ConditionContextVO
        from app.model.vo.monthly_limit_vo import MonthlyLimitVO

        return ConditionContextVO(
            self.bank_code, option.saving_term_months, MonthlyLimitVO.from_database(self.monthly_limit)
        )
