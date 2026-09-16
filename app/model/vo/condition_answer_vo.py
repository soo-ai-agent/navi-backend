from __future__ import annotations
from dataclasses import dataclass
from app.constants.saving_condition import MAX_CONDITION_AGE
from app.enums.answer_value import AnswerStatus, YesNoAnswer
from app.enums.saving_condition import BANK_LIST_FIELDS, NO_BANK_ANSWER, BankAnswer, ConditionField
from app.model.vo.answers_vo import AnswersVO
from app.model.vo.condition_context_vo import ConditionContextVO

_SHARED_ANSWER_KEYS: dict[ConditionField, str] = {
    ConditionField.MONTHLY_DEPOSIT: "monthly",
    ConditionField.SAVING_TERM: "months",
}
"""필드 이름과 다른 답변 키를 쓰는 질문들. 나머지는 필드 값을 그대로 키로 쓴다"""

_CUSTOMER_TYPES: tuple[str, ...] = ("individual", "business")

"""사람이 답할 수 있는 나이의 상한. 넘으면 잘못 입력한 것으로 본다"""

MAX_NUMBER_LENGTH = 18
"""숫자 답의 최대 자릿수. 화면이 문자열로 보내는 값을 정수로 바꿀 때의 상한이다"""


@dataclass(frozen=True)
class ConditionAnswerVO:
    field: ConditionField
    context: ConditionContextVO
    # other 조건은 공시 원문마다 질문이 달라서 AI 가 질문 키와 문장을 함께 보존한다.
    question_key: str = ""
    question_text: str = ""

    @property
    def key(self) -> str:
        if self.field is ConditionField.OTHER:
            return self.question_key

        # 카드 사용액만 은행별로 따로 답한다. 나머지 은행 질문은 한 번 고른 답을 모든 상품이 함께 쓴다.
        if self.field is ConditionField.CARD_SPEND:
            return f"{self.field.value}:{self.context.bank_code}"

        return _SHARED_ANSWER_KEYS.get(self.field, self.field.value)

    def number_value(self, answers: AnswersVO) -> int | AnswerStatus:
        if self.field is ConditionField.SAVING_TERM:
            return self.context.saving_term_months

        answer: str | AnswerStatus = answers.value_of(self.key)
        if isinstance(answer, AnswerStatus):
            return answer

        if not self._is_number(answer):
            return AnswerStatus.INVALID

        # HTTP 답변 계약이 문자열이므로 검증된 숫자 문자열만 여기서 한 번 변환한다.
        number: int = int(answer)

        if self.field is ConditionField.AGE and number > MAX_CONDITION_AGE:
            return AnswerStatus.INVALID

        if self.field is ConditionField.MONTHLY_DEPOSIT:
            return self.context.planned_monthly_deposit(number)

        return number

    @staticmethod
    def _is_number(answer: str) -> bool:
        if not answer.isascii():
            return False
        if not answer.isdecimal():
            return False
        return len(answer) <= MAX_NUMBER_LENGTH

    def text_value(self, answers: AnswersVO) -> str | AnswerStatus:
        answer: str | AnswerStatus = answers.value_of(self.key)
        if isinstance(answer, AnswerStatus):
            return answer

        if self.field is ConditionField.CUSTOMER_TYPE:
            return self._customer_type(answer)

        if self.field in BANK_LIST_FIELDS:
            return self._bank_from_list(answer)

        return self._bank_from_yes_no(answer)

    @staticmethod
    def _customer_type(answer: str) -> str | AnswerStatus:
        if answer in _CUSTOMER_TYPES:
            return answer
        return AnswerStatus.INVALID

    def _bank_from_list(self, answer: str) -> str:
        if answer == NO_BANK_ANSWER:
            return BankAnswer.NO_BANK.value

        for code in answer.split(","):
            if code.strip() == self.context.bank_code:
                return BankAnswer.PRODUCT_BANK.value

        return BankAnswer.NO_BANK.value

    @staticmethod
    def _bank_from_yes_no(answer: str) -> str | AnswerStatus:
        if answer == YesNoAnswer.YES:
            return BankAnswer.PRODUCT_BANK.value

        if answer == YesNoAnswer.NO:
            return BankAnswer.NO_BANK.value

        return AnswerStatus.INVALID

    def boolean_value(self, answers: AnswersVO) -> bool | AnswerStatus:
        answer: str | AnswerStatus = answers.value_of(self.key)
        if isinstance(answer, AnswerStatus):
            return answer

        if answer == YesNoAnswer.YES:
            return True

        if answer == YesNoAnswer.NO:
            return False

        return AnswerStatus.INVALID
