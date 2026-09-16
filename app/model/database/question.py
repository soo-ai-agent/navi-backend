from __future__ import annotations
from sqlalchemy import Boolean, Enum as SAEnum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from app.enums.answer_kind import AnswerKind
from app.enums.judge_kind import JudgeKind
from app.model.database.base import Base


class Question(Base):
    __tablename__ = "question"
    # SQLAlchemy가 테이블 옵션을 dict 형식으로 요구한다.
    __table_args__ = {"comment": "질문 목록. 우대조건(product_bonus)이 answer_code 로 가리킨다"}

    code: Mapped[str] = mapped_column(
        String(64), primary_key=True, comment="답이 실릴 키. 클라이언트가 이 값으로 답을 보낸다"
    )
    title: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="사용자에게 보여줄 질문 문장"
    )
    answer_kind: Mapped[AnswerKind] = mapped_column(
        SAEnum(AnswerKind, native_enum=False), nullable=False,
        comment="답을 받는 형식 — 자유입력·선다형·숫자·예아니오"
    )
    judge_kind: Mapped[JudgeKind] = mapped_column(
        SAEnum(JudgeKind, native_enum=False), nullable=False,
        comment="받은 답을 어떻게 쓰는가 — 코드가 아는 다섯 가지 중 하나"
    )
    ask_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="후보를 좁히는 질문을 묻는 순서. 작을수록 먼저"
    )
    inverted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
        comment="이 질문으로 분류된 조건은 판정을 뒤집는다. 거래한 적 없어야 받는 신규고객 우대가 이 경우다"
    )
