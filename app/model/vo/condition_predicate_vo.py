from __future__ import annotations

from typing import assert_never

from pydantic import Field, GetJsonSchemaHandler, StrictBool, StrictInt, StrictStr, TypeAdapter, model_validator
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import CoreSchema

from app.constants.saving_condition import MAX_CONDITION_AGE, MIN_CONDITION_NUMBER
from app.enums.answer_value import AnswerStatus
from app.enums.saving_condition import ConditionField, ConditionOperator
from app.enums.saving import BonusResult
from app.exception.condition import ConditionVerificationError
from app.model.vo.answers_vo import AnswersVO
from app.model.vo.condition_answer_vo import ConditionAnswerVO
from app.model.vo.condition_context_vo import ConditionContextVO
from app.model.vo.condition_evidence_vo import ConditionEvidenceVO


class ConditionPredicateVO(ConditionEvidenceVO):
    field: ConditionField
    operator: ConditionOperator
    # LLM 공통 JSON의 values는 field에 따라 종류가 달라진다. 수신 시 정확한 타입을 검사하고 판정은 타입별로 나눈다.
    values: tuple[StrictInt | StrictStr | StrictBool, ...] = Field(min_length=1, max_length=2)
    # 공시 문장을 기존 필드로 표현할 수 없을 때 사용할 사용자 확인 질문이다.
    question_key: str = Field(default="", max_length=100)
    question_text: str = Field(default="", max_length=300)

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema: CoreSchema, handler: GetJsonSchemaHandler) -> JsonSchemaValue:
        # Pydantic의 JSON Schema 확장 API는 dict 기반이다. 외부에 전달할 스키마를 만드는 경계에서만 사용한다.
        schema: JsonSchemaValue = handler(core_schema)
        rules: list[JsonSchemaValue] = []
        for field in ConditionField:
            value_schema: JsonSchemaValue = TypeAdapter(field.value_type()).json_schema()
            if field.value_type() is str:
                value_schema["enum"] = list(field.allowed_text_values())
            if field.value_type() is int:
                value_schema["minimum"] = MIN_CONDITION_NUMBER
            if field is ConditionField.AGE:
                value_schema["maximum"] = MAX_CONDITION_AGE
            then_schema: JsonSchemaValue = {"properties": {
                "values": {"items": value_schema},
                "operator": {"enum": [operator.value for operator in field.allowed_operators()]},
            }}
            if field is ConditionField.OTHER:
                then_schema["required"] = ["question_key", "question_text"]
            rules.append({
                "if": {"properties": {"field": {"const": field.value}}},
                "then": then_schema,
            })
        for operator in ConditionOperator:
            count: int = operator.value_count()
            rules.append({
                "if": {"properties": {"operator": {"const": operator.value}}},
                "then": {"properties": {"values": {"minItems": count, "maxItems": count}}},
            })
        schema["allOf"] = rules
        return schema

    @model_validator(mode="after")
    def validate_values(self) -> ConditionPredicateVO:
        self._validate_value_count()
        self._validate_operator()
        self._validate_question()
        for value in self.values:
            if type(value) is not self.field.value_type():
                raise ConditionVerificationError(
                    f"{self.field.value} 조건은 {self.field.value_type().__name__} 값이 필요하지만 "
                    f"{type(value).__name__} 값이 반환됐습니다."
                )
            if type(value) is int:
                self._validate_number(value)
            elif type(value) is str:
                self._validate_text(value)
        self._validate_range()
        return self

    def _validate_question(self) -> None:
        if self.field is ConditionField.OTHER:
            if not self.question_key.strip() or not self.question_text.strip():
                raise ValueError("표현할 수 없는 조건은 질문 키와 질문 문장이 필요합니다")
            return
        if self.question_key or self.question_text:
            raise ValueError("질문 키와 질문 문장은 other 조건에서만 사용합니다")

    def _validate_value_count(self) -> None:
        expected_count: int = self.operator.value_count()
        if len(self.values) != expected_count:
            raise ValueError("연산자와 기준값 개수가 다릅니다")

    def _validate_operator(self) -> None:
        if self.operator not in self.field.allowed_operators():
            raise ValueError("문자열·불리언은 동등 비교만 지원합니다")

    def _validate_number(self, value: int) -> None:
        if value < MIN_CONDITION_NUMBER:
            raise ValueError("나이·기간·금액은 음수가 아닌 정수여야 합니다")
        if self.field is ConditionField.AGE and value > MAX_CONDITION_AGE:
            raise ValueError("나이 범위를 확인해야 합니다")

    def _validate_text(self, value: str) -> None:
        if value in self.field.allowed_text_values():
            return
        if self.field is ConditionField.CUSTOMER_TYPE:
            raise ValueError("지원하지 않는 고객 구분입니다")
        raise ValueError("은행 조건은 해당 상품 은행으로 한정합니다")

    def _validate_range(self) -> None:
        if self.operator is not ConditionOperator.BETWEEN:
            return
        lower, upper = self.values
        if type(lower) is int and type(upper) is int and lower > upper:
            raise ValueError("범위의 상한이 하한보다 작습니다")

    def evaluate(self, answers: AnswersVO, context: ConditionContextVO) -> BonusResult:
        answer: ConditionAnswerVO = self._answer(context)

        if type(self.values[0]) is int:
            number: int | AnswerStatus = answer.number_value(answers)
            if isinstance(number, AnswerStatus):
                return BonusResult.UNKNOWN
            return self._bonus_result(self._matches_number(number))

        if type(self.values[0]) is str:
            text: str | AnswerStatus = answer.text_value(answers)
            if isinstance(text, AnswerStatus):
                return BonusResult.UNKNOWN
            return self._bonus_result(self._matches_equality(text))

        boolean: bool | AnswerStatus = answer.boolean_value(answers)
        if isinstance(boolean, AnswerStatus):
            return BonusResult.UNKNOWN
        return self._bonus_result(self._matches_equality(boolean))

    @staticmethod
    def _bonus_result(eligible: bool) -> BonusResult:
        if eligible:
            return BonusResult.ELIGIBLE
        return BonusResult.NOT_ELIGIBLE

    def _matches_equality(self, value: str | bool) -> bool:
        same: bool = value == self.values[0]
        if self.operator is ConditionOperator.NE:
            return not same
        return same

    def _matches_number(self, value: int) -> bool:
        if type(self.values[0]) is not int:
            raise ValueError("숫자 기준값이 필요합니다")
        lower: int = self.values[0]
        match self.operator:
            case ConditionOperator.EQ:
                return value == lower
            case ConditionOperator.NE:
                return value != lower
            case ConditionOperator.GTE:
                return value >= lower
            case ConditionOperator.LTE:
                return value <= lower
            case ConditionOperator.BETWEEN:
                if type(self.values[1]) is not int:
                    raise ValueError("숫자 상한이 필요합니다")
                upper: int = self.values[1]
                return lower <= value <= upper
            case _:
                assert_never(self.operator)

    def unanswered(self, answers: AnswersVO, context: ConditionContextVO) -> tuple[ConditionAnswerVO, ...]:
        answer: ConditionAnswerVO = self._answer(context)

        if self.evaluate(answers, context) is not BonusResult.UNKNOWN:
            return ()

        if answers.contains(answer.key):
            return ()

        return (answer,)

    def _answer(self, context: ConditionContextVO) -> ConditionAnswerVO:
        return ConditionAnswerVO(self.field, context, self.question_key, self.question_text)
