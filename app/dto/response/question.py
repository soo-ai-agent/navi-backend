from __future__ import annotations

from typing import TYPE_CHECKING, TypeAlias, assert_never

from pydantic import BaseModel, ConfigDict

from app.constants.question_text import (
    AGE_OPTIONS, CARD_SPEND_OPTIONS, GOAL_AMOUNT_KEY, PERFORMANCE_MONTHS_OPTIONS, MONTHLY_DEPOSIT_OPTIONS, UNKNOWN_OPTION, PRINCIPAL_OPTIONS, YES_NO_OPTIONS,
)
from app.enums.answer_kind import AnswerKind
from app.enums.answer_value import AnswerStatus
from app.enums.saving_condition import BANK_LIST_FIELDS, NO_BANK_ANSWER, ConditionField

if TYPE_CHECKING:
    from app.model.vo.banks_vo import BanksVO
    from app.model.vo.questions_vo import QuestionsVO
    from app.model.vo.saving_products_vo import SavingProductsVO
    from app.model.vo.condition_answer_vo import ConditionAnswerVO

QuestionOption: TypeAlias = tuple[str, str]
"""선택지 하나 — (보낼 값, 보여줄 말). 값은 그대로 답이 되어 돌아온다"""

SAVING_TERM_KEY = "months"
MONTHLY_DEPOSIT_KEY = "monthly"

_NUMBER_OPTIONS: dict[ConditionField, tuple[QuestionOption, ...]] = {
    ConditionField.AGE: AGE_OPTIONS,
    ConditionField.MONTHLY_DEPOSIT: MONTHLY_DEPOSIT_OPTIONS,
    ConditionField.PRINCIPAL: PRINCIPAL_OPTIONS,
    ConditionField.CARD_SPEND: CARD_SPEND_OPTIONS,
    ConditionField.PERFORMANCE_MONTHS: PERFORMANCE_MONTHS_OPTIONS,
}

_CUSTOMER_TYPE_OPTIONS: tuple[QuestionOption, ...] = (("individual", "개인"), ("business", "사업자"))

NO_BANK_OPTION: tuple[QuestionOption, ...] = ((NO_BANK_ANSWER, "해당 없음"),)


class QuestionResponseDTO(BaseModel):
    """사용자에게 보여줄 질문 하나."""

    model_config = ConfigDict(frozen=True)

    key: str

    title: str
    answer_kind: AnswerKind

    options: tuple[QuestionOption, ...]

    def offers(self, value: str) -> bool:
        return any(option_value == value for option_value, _label in self.options)

    @classmethod
    def from_condition(cls, answer: ConditionAnswerVO, bank_name: str, banks: BanksVO) -> QuestionResponseDTO:
        kind, options = cls._answer_kind_with_options(answer.field, banks)
        return cls(
            key=answer.key,
            title=cls._condition_title(answer, bank_name),
            answer_kind=kind,
            options=options,
        )

    @staticmethod
    def _condition_title(answer: ConditionAnswerVO, bank_name: str) -> str:
        match answer.field:
            case ConditionField.AGE:
                return "나이가 어떻게 되세요? (만)"
            case ConditionField.MONTHLY_DEPOSIT:
                return "매달 얼마씩 넣을까요? (원)"
            case ConditionField.PRINCIPAL:
                return "만기까지 모을 원금은 얼마인가요? (원)"
            case ConditionField.SAVING_TERM:
                return "얼마 동안 넣을까요? (개월)"
            case ConditionField.CUSTOMER_TYPE:
                return "어떤 고객 구분으로 가입하시나요?"
            case ConditionField.SALARY_BANK:
                return "급여나 연금은 어느 은행으로 받으세요?"
            case ConditionField.EXISTING_BANK:
                return "예금이나 적금을 이미 갖고 있는 은행을 골라 주세요."
            case ConditionField.CARD_BANK:
                return "신용·체크카드는 어느 은행 것을 쓰세요?"
            case ConditionField.PAYMENT_ACCOUNT_BANK:
                return "급여·자동이체·카드결제의 출금계좌는 어느 은행인가요?"
            case ConditionField.CARD_SPEND:
                return f"{bank_name} 카드의 월 사용액은 얼마인가요? (원)"
            case ConditionField.AUTOPAY:
                return "공과금을 자동이체로 내고 계세요?"
            case ConditionField.MOBILE:
                return "인터넷이나 앱으로 가입하시나요?"
            case ConditionField.MARKETING:
                return "마케팅 정보 수신에 동의하시나요?"
            case ConditionField.PERFORMANCE_MONTHS:
                return "우대조건 실적을 몇 개월 채울 수 있으세요? (개월)"
            case ConditionField.OTHER:
                return answer.question_text
            case _:
                assert_never(answer.field)

    @staticmethod
    def _answer_kind_with_options(
            field: ConditionField, banks: BanksVO,
    ) -> tuple[AnswerKind, tuple[QuestionOption, ...]]:
        # 숫자로 답하는 질문은 모두 "모르겠어요"를 함께 준다 — 모르는 값을 지어내게 하지 않는다.
        if field.value_type() is int:
            presets: tuple[QuestionOption, ...] = _NUMBER_OPTIONS.get(field, ())
            return AnswerKind.NUMBER_WITH_OPTIONS, presets + UNKNOWN_OPTION

        if field is ConditionField.CUSTOMER_TYPE:
            return AnswerKind.OPTIONS, _CUSTOMER_TYPE_OPTIONS

        if field in BANK_LIST_FIELDS:
            bank_options = tuple((bank.bank_code, bank.display_name) for bank in banks.banks)
            return AnswerKind.MULTI_OPTIONS, bank_options + NO_BANK_OPTION

        return AnswerKind.BOOLEAN, YES_NO_OPTIONS

    @classmethod
    def for_saving_terms(cls, products: SavingProductsVO, questions: QuestionsVO) -> QuestionResponseDTO:
        options: list[QuestionOption] = []
        # HTTP 선택지의 키는 문자열 계약이므로 기간을 응답 경계에서만 문자열로 만든다.
        for term in products.available_saving_terms():
            options.append((str(term), f"{term}개월"))

        options.append((AnswerStatus.SKIPPED.value, "상관없어요"))

        return cls(
            key=SAVING_TERM_KEY,
            title=questions.title(SAVING_TERM_KEY, "얼마 동안 넣을까요?"),
            answer_kind=AnswerKind.OPTIONS,
            options=tuple(options),
        )

    @classmethod
    def for_monthly_deposit(cls, questions: QuestionsVO) -> QuestionResponseDTO:
        return cls(
            key=MONTHLY_DEPOSIT_KEY,
            title=questions.title(MONTHLY_DEPOSIT_KEY, "매달 얼마씩 넣을까요? (원)"),
            answer_kind=AnswerKind.NUMBER_WITH_OPTIONS,
            options=MONTHLY_DEPOSIT_OPTIONS + UNKNOWN_OPTION,
        )

    @classmethod
    def for_goal_amount(cls, questions: QuestionsVO) -> QuestionResponseDTO:
        no_goal_option: tuple[QuestionOption, ...] = ((AnswerStatus.SKIPPED.value, "목표 금액은 없어요"),)

        return cls(
            key=GOAL_AMOUNT_KEY,
            title=questions.title(GOAL_AMOUNT_KEY, "만기까지 모으고 싶은 금액이 있나요? (원)"),
            answer_kind=AnswerKind.NUMBER_WITH_OPTIONS,
            options=PRINCIPAL_OPTIONS + no_goal_option,
        )
