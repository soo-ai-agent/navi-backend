from __future__ import annotations
from decimal import Decimal
from typing import TYPE_CHECKING
from sqlalchemy import Enum as SAEnum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.enums.saving import InterestCalcType, ReserveType
from app.model.database.base import Base

if TYPE_CHECKING:
    from app.model.database.saving import Saving


class RateOption(Base):
    """기간·적립방식별 금리. 금리가 빈 옵션은 적재하지 않으므로 두 금리 모두 non-null 이다."""

    __tablename__ = "rate_option"
    # SQLAlchemy가 테이블 옵션을 dict 형식으로 요구한다.
    __table_args__ = {"comment": "금리 옵션. 상품 하나에 기간·적립방식별로 여러 건이 붙는다"}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, comment="금리 옵션 일련번호")
    product_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("product.product_id"), nullable=False, index=True,
        comment="상품 식별자"
    )
    saving_term_months: Mapped[int] = mapped_column(nullable=False, comment="저축 기간(개월)")
    reserve_type: Mapped[ReserveType] = mapped_column(
        SAEnum(ReserveType, native_enum=False), nullable=False,
        comment="적립 방식 — 정액적립식·자유적립식"
    )
    interest_calc_type: Mapped[InterestCalcType] = mapped_column(
        SAEnum(InterestCalcType, native_enum=False), nullable=False,
        comment="이자 계산 방식 — 단리·복리"
    )
    base_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, comment="기본금리(%)"
    )
    max_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, comment="최고우대금리(%). 우대조건을 다 채웠을 때의 상한"
    )

    saving: Mapped[Saving] = relationship(back_populates="rate_options")

    def rate_with(self, bonus_points: Decimal) -> Decimal:
        """
        우대를 더한 금리. 공시 상한(max_rate)을 넘지 않는다.

        항목을 다 더하면 상한을 넘는 상품이 있다 — 중복 적용 불가 조건이 섞여 있기 때문이다.
        """
        return min(self.base_rate + bonus_points, self.max_rate)
