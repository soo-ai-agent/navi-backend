from __future__ import annotations
from decimal import Decimal
from typing import TYPE_CHECKING, Sequence
from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.model.database.base import Base
from app.enums.judge_kind import JudgeKind
from app.enums.saving_condition import BankAnswer, ConditionOperator, ConditionField
from app.model.vo.condition_group_vo import ConditionGroupVO
from app.model.vo.condition_predicate_vo import ConditionPredicateVO
from app.model.vo.extracted_conditions_vo import ExtractedConditionsVO

if TYPE_CHECKING:
    from app.model.database.saving import Saving
    from app.model.database.question import Question


_MINIMUM_JUDGE_KINDS: dict[ConditionField, JudgeKind] = {
    ConditionField.AGE: JudgeKind.AGE,
    ConditionField.MONTHLY_DEPOSIT: JudgeKind.MONTHLY,
    ConditionField.PRINCIPAL: JudgeKind.PRINCIPAL,
    ConditionField.PERFORMANCE_MONTHS: JudgeKind.PERFORMANCE_MONTHS,
}
"""'기준값 이상'으로 판정하는 필드들"""

_SAVING_BANK_JUDGE_KINDS: dict[ConditionField, JudgeKind] = {
    ConditionField.SALARY_BANK: JudgeKind.SALARY,
    ConditionField.CARD_BANK: JudgeKind.CARD,
    ConditionField.PAYMENT_ACCOUNT_BANK: JudgeKind.PAYMENT_ACCOUNT,
}
"""'이 상품의 은행인가'로 판정하는 필드들"""

_YES_JUDGE_KINDS: dict[ConditionField, JudgeKind] = {
    ConditionField.AUTOPAY: JudgeKind.AUTOPAY,
    ConditionField.MOBILE: JudgeKind.MOBILE,
    ConditionField.MARKETING: JudgeKind.MARKETING,
}
"""'예라고 답했는가'로 판정하는 필드들"""


class SavingBonus(Base):
    __tablename__ = "product_bonus"
    # SQLAlchemy가 테이블 옵션을 dict 형식으로 요구한다.
    __table_args__ = {"comment": "구조화된 우대조건. 공시 원문을 배치가 번역한다"}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, comment="우대조건 일련번호")
    product_id: Mapped[str] = mapped_column(String(64), ForeignKey("product.product_id"), nullable=False, index=True, comment="상품 식별자")
    answer_code: Mapped[str] = mapped_column(String(64), ForeignKey("question.code"), nullable=False, index=True, comment="이 조건을 풀려면 받아야 하는 답 — question 테이블의 질문을 가리킨다")
    percentage_point: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, comment="이 조건을 채웠을 때 더해지는 금리(%p)")
    label: Mapped[str] = mapped_column(String(255), nullable=False, comment="화면에 보여줄 짧은 이름")
    required_amount: Mapped[int | None] = mapped_column(nullable=True, comment="금액·나이 하한. null은 하한 조건 없음이며 기준값 0과 구분한다")
    saving_term_months: Mapped[int | None] = mapped_column(nullable=True, comment="이 조건이 붙는 저축 기간(개월). null 이면 전 기간 공통")
    saving: Mapped[Saving] = relationship(back_populates="bonuses")

    @classmethod
    def from_conditions(
            cls, product_id: str, extracted: ExtractedConditionsVO, questions: Sequence[Question]
    ) -> list[SavingBonus]:
        bonuses: list[SavingBonus] = []
        for bonus in extracted.bonuses:
            predicate: ConditionPredicateVO | None = cls._single_predicate(bonus.condition)
            if predicate is None:
                continue

            judge_kind: JudgeKind | None = cls._judge_kind(predicate)
            if judge_kind is None:
                continue

            question: Question | None = cls._question_for(judge_kind, questions)
            if question is None:
                continue

            bonuses.append(cls(
                product_id=product_id, answer_code=question.code,
                percentage_point=bonus.percentage_point, label=bonus.label,
                required_amount=cls._required_amount(predicate), saving_term_months=None,
            ))
        return bonuses

    @staticmethod
    def _single_predicate(condition: ConditionGroupVO) -> ConditionPredicateVO | None:
        """조건 하나로 이뤄진 우대만 구형 형식으로 옮길 수 있다. 아니면 None 으로 알린다."""
        if len(condition.conditions) != 1:
            return None

        only: ConditionPredicateVO | ConditionGroupVO = condition.conditions[0]
        if not isinstance(only, ConditionPredicateVO):
            return None

        return only

    @staticmethod
    def _question_for(judge_kind: JudgeKind, questions: Sequence[Question]) -> Question | None:
        """이 판정 방식을 쓰는 첫 질문. 질문이 없으면 None 으로 알려 저장을 건너뛴다."""
        for question in questions:
            if question.judge_kind is judge_kind:
                return question
        return None

    @staticmethod
    def _required_amount(predicate: ConditionPredicateVO) -> int | None:
        """금액·나이 하한. 하한 조건이 없는 우대를 기준값 0 과 구분하려고 None 을 쓴다."""
        if predicate.operator is not ConditionOperator.GTE:
            return None
        if type(predicate.values[0]) is not int:
            return None
        return predicate.values[0]

    @staticmethod
    def _judge_kind(predicate: ConditionPredicateVO) -> JudgeKind | None:
        """
        이 조건을 구형 판정 방식 중 무엇으로 옮길지 고른다.

        비교 방식과 기준값이 아래 셋 중 하나와 맞아야 한다. 아니면 None 으로 알려 호환 저장에서 제외한다.
        """
        if predicate.operator is ConditionOperator.GTE:
            return _MINIMUM_JUDGE_KINDS.get(predicate.field)

        if predicate.operator is not ConditionOperator.EQ:
            return None

        if predicate.values == (BankAnswer.PRODUCT_BANK.value,):
            return _SAVING_BANK_JUDGE_KINDS.get(predicate.field)

        if predicate.values == (True,):
            return _YES_JUDGE_KINDS.get(predicate.field)

        return None
