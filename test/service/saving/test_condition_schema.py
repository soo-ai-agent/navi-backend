from __future__ import annotations
from unittest import TestCase
from pydantic import ValidationError
from app.enums.saving_condition import ConditionField, ConditionOperator, ConditionSourceField
from app.model.vo.condition_predicate_vo import ConditionPredicateVO
from app.model.vo.extracted_conditions_vo import ExtractedConditionsVO


class TestConditionSchema(TestCase):
    def test_숫자와_불리언_필드의_자료형을_스키마에_명시한다(self):
        # 외부로 전달되는 JSON Schema 계약을 확인한다.
        schema = ExtractedConditionsVO.model_json_schema()
        rules = schema["$defs"]["ConditionPredicateVO"]["allOf"]
        self.assertEqual(20, len(rules))
        for field, items, operators in (
            ("age", {"type": "integer", "minimum": 0, "maximum": 120}, ["eq", "ne", "gte", "lte", "between"]),
            ("monthly_deposit", {"type": "integer", "minimum": 0}, ["eq", "ne", "gte", "lte", "between"]),
            ("saving_term", {"type": "integer", "minimum": 0}, ["eq", "ne", "gte", "lte", "between"]),
            ("principal", {"type": "integer", "minimum": 0}, ["eq", "ne", "gte", "lte", "between"]),
            ("card_spend_at_product_bank", {"type": "integer", "minimum": 0}, ["eq", "ne", "gte", "lte", "between"]),
            ("autopay", {"type": "boolean"}, ["eq", "ne"]),
            ("mobile", {"type": "boolean"}, ["eq", "ne"]),
            ("marketing", {"type": "boolean"}, ["eq", "ne"]),
            ("performance_months", {"type": "integer", "minimum": 0}, ["eq", "ne", "gte", "lte", "between"]),
        ):
            with self.subTest(field=field):
                self.assertIn({
                    "if": {"properties": {"field": {"const": field}}},
                    "then": {"properties": {"values": {"items": items}, "operator": {"enum": operators}}},
                }, rules)

    def test_연산자별_기준값_개수를_스키마에_명시한다(self):
        # 외부로 전달되는 JSON Schema 계약을 확인한다.
        rules = ExtractedConditionsVO.model_json_schema()["$defs"]["ConditionPredicateVO"]["allOf"]
        for operator, count in (("eq", 1), ("ne", 1), ("gte", 1), ("lte", 1), ("between", 2)):
            with self.subTest(operator=operator):
                self.assertIn({
                    "if": {"properties": {"operator": {"const": operator}}},
                    "then": {"properties": {"values": {"minItems": count, "maxItems": count}}},
                }, rules)

    def test_숫자와_불리언_값을_형변환하지_않는다(self):
        for field, value in (
            (ConditionField.AGE, "19"), (ConditionField.AGE, True),
            (ConditionField.CARD_SPEND, "3000000"),
            (ConditionField.AUTOPAY, "true"), (ConditionField.MOBILE, 1),
            (ConditionField.MARKETING, "PRODUCT_BANK"),
        ):
            with self.subTest(field=field, value=value), self.assertRaises(ValidationError):
                ConditionPredicateVO(
                    field=field, operator=ConditionOperator.EQ, values=(value,),
                    source_field=ConditionSourceField.BONUS, source_text="조건 원문",
                )

    def test_추출_스키마가_문자열_조건의_허용값을_명시한다(self):
        # Pydantic JSON Schema의 외부 계약을 검증하므로 dict 형태로 확인한다.
        schema = ExtractedConditionsVO.model_json_schema()
        rules = schema["$defs"]["ConditionPredicateVO"]["allOf"]
        expected = (
            ("customer_type", ["individual", "business"]),
            ("salary_bank", ["PRODUCT_BANK"]),
            ("existing_bank", ["PRODUCT_BANK"]),
            ("card_bank", ["PRODUCT_BANK"]),
        )
        for field, values in expected:
            with self.subTest(field=field):
                self.assertIn({
                    "if": {"properties": {"field": {"const": field}}},
                    "then": {"properties": {
                        "values": {"items": {"type": "string", "enum": values}},
                        "operator": {"enum": ["eq", "ne"]},
                    }},
                }, rules)

    def test_표현할_수_없는_조건은_사용자_질문을_필수로_한다(self):
        rules = ExtractedConditionsVO.model_json_schema()["$defs"]["ConditionPredicateVO"]["allOf"]
        self.assertIn({
            "if": {"properties": {"field": {"const": "other"}}},
            "then": {
                "properties": {
                    "values": {"items": {"type": "boolean"}},
                    "operator": {"enum": ["eq", "ne"]},
                },
                "required": ["question_key", "question_text"],
            },
        }, rules)

    def test_허용된_문자열_조건을_그대로_읽는다(self):
        for field, value in (
            (ConditionField.SALARY_BANK, "PRODUCT_BANK"),
            (ConditionField.EXISTING_BANK, "PRODUCT_BANK"),
            (ConditionField.CARD_BANK, "PRODUCT_BANK"),
            (ConditionField.CUSTOMER_TYPE, "individual"),
            (ConditionField.CUSTOMER_TYPE, "business"),
        ):
            with self.subTest(field=field, value=value):
                condition = ConditionPredicateVO(
                    field=field, operator=ConditionOperator.EQ, values=(value,),
                    source_field=ConditionSourceField.BONUS, source_text="조건 원문",
                )
                self.assertEqual((value,), condition.values)

    def test_필드에_맞지_않는_문자열을_거부한다(self):
        for field, value in (
            (ConditionField.SALARY_BANK, "우리은행"),
            (ConditionField.EXISTING_BANK, "individual"),
            (ConditionField.CARD_BANK, "business"),
            (ConditionField.CUSTOMER_TYPE, "PRODUCT_BANK"),
        ):
            with self.subTest(field=field, value=value), self.assertRaises(ValidationError):
                ConditionPredicateVO(
                    field=field, operator=ConditionOperator.EQ, values=(value,),
                    source_field=ConditionSourceField.BONUS, source_text="조건 원문",
                )
