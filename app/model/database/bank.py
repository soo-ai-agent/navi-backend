from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.model.database.base import Base


class Bank(Base):
    __tablename__ = "bank"
    # SQLAlchemy가 테이블 옵션을 dict 형식으로 요구한다.
    __table_args__ = {"comment": "은행. 공시 금융회사 API 로 채운다"}

    bank_code: Mapped[str] = mapped_column(String(16), primary_key=True, comment="은행 코드 (공시 fin_co_no)")
    original_name: Mapped[str] = mapped_column(String(64), nullable=False, comment="공시가 준 은행명 원문 (공시 kor_co_nm)")
    display_name: Mapped[str] = mapped_column(String(64), nullable=False, comment="법인 표기를 정리한 화면용 이름")
    homepage_url: Mapped[str] = mapped_column(String(255), nullable=False, default='', comment="홈페이지 주소. 공시에 비어 오는 회사가 있어 빈 문자열을 허용한다")
    call_center: Mapped[str] = mapped_column(String(64), nullable=False, default='', comment="콜센터 번호. 공시에 비어 오는 회사가 있다")
