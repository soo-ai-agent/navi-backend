from __future__ import annotations
from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.model.database.base import Base
from app.model.vo.wish_structure_vo import WishStructureVO


class UserWish(Base):
    __tablename__ = "user_wish"
    # SQLAlchemy가 테이블 옵션을 dict 형식으로 요구한다.
    __table_args__ = {"comment": "사용자가 원한다고 말한 적금 조건과 그 구조화 결과"}
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    message: Mapped[str] = mapped_column(String(1000), nullable=False, comment="사용자가 보낸 원문 그대로")
    structured_json: Mapped[str] = mapped_column(
        Text, nullable=False, comment="구조화 결과(WishStructureVO JSON). 매핑된 답과 보존한 요구를 함께 담는다"
    )

    @classmethod
    def from_structured(cls, message: str, structured: WishStructureVO) -> UserWish:
        return cls(message=message, structured_json=structured.model_dump_json())

    def read_structured(self) -> WishStructureVO:
        return WishStructureVO.model_validate_json(self.structured_json)
