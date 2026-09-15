from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
from unittest import TestCase

from pydantic import ValidationError

from app.enums.saving_condition import BonusConditionStatus, ConditionField, ConditionMatch, ConditionOperator, ConditionSourceField, ConditionStatus
from app.enums.saving import JoinRestriction
from app.model.database.saving_condition import SavingCondition
from app.model.vo.condition_group_vo import ConditionGroupVO
from app.model.vo.condition_predicate_vo import ConditionPredicateVO
from app.constants.saving_condition import CONDITION_SCHEMA_VERSION
from app.model.vo.extracted_conditions_vo import ExtractedConditionsVO
from app.model.vo.saving_condition_source_vo import SavingConditionSourceVO
from app.model.vo.answers_vo import AnswersVO
from app.model.vo.condition_context_vo import ConditionContextVO
from app.model.vo.monthly_limit_vo import MonthlyLimitVO


def source() -> SavingConditionSourceVO:
    return SavingConditionSourceVO(
        product_id="bank:P1", name="청년적금", join_member="만 19~34세 개인",
        join_restriction=JoinRestriction.PARTIAL, join_ways="앱",
        spcl_cnd="급여이체 시 0.7%p", etc_note="", monthly_limit=500000,
        saving_terms=(12,), max_bonus_point=Decimal("0.7"),
    )


# 잘못된 LLM JSON도 만들어 검증해야 하므로 검증된 모델 대신 dict를 사용한다.
def answer() -> dict:
    return {
        "eligibility": {"match": "all", "conditions": [
            {"field": "age", "operator": "between", "values": [19, 34],
             "source_field": "join_member", "source_text": "만 19~34세 개인"},
        ]},
        "bonuses": [{"label": "급여이체", "percentage_point": "0.7", "condition": {
            "match": "all", "conditions": [
                {"field": "salary_bank", "operator": "eq", "values": ["PRODUCT_BANK"],
                 "source_field": "spcl_cnd", "source_text": "급여이체 시 0.7%p"},
            ],
        }}],
        "unresolved": [],
    }


class TestSavingConditions(TestCase):
    def test_우대금리_없음_상태를_명시하면_완료로_저장한다(self):
        no_bonus_source = source().model_copy(update={
            "spcl_cnd": "해당없음", "max_bonus_point": Decimal("0"),
            "join_restriction": JoinRestriction.ANYONE,
        })
        extracted = ExtractedConditionsVO(
            eligibility=ConditionGroupVO(match=ConditionMatch.ALL, conditions=()), bonuses=(), unresolved=(),
            bonus_status=BonusConditionStatus.NO_BONUS,
        )
        extracted.verify(no_bonus_source)
        self.assertFalse(extracted.needs_review(no_bonus_source))
        self.assertEqual(BonusConditionStatus.NO_BONUS, extracted.bonus_status)

    def test_표현할_수_없는_조건은_질문으로_판정한다(self):
        condition = ConditionPredicateVO(
            field=ConditionField.OTHER, operator=ConditionOperator.EQ, values=(True,),
            question_key="other_salary_months", question_text="급여이체를 6개월 이상 유지할 수 있나요?",
            source_field=ConditionSourceField.BONUS, source_text="급여이체를 6개월 이상 유지",
        )
        unanswered = condition.unanswered(AnswersVO(()), ConditionContextVO("bank", 12, MonthlyLimitVO.limited(500000)))
        self.assertEqual("other_salary_months", unanswered[0].key)

    def test_나이_범위와_우대조건을_근거와_함께_보존한다(self):
        extracted = ExtractedConditionsVO.model_validate(answer())
        extracted.verify(source())

        self.assertEqual((19, 34), extracted.eligibility.predicates()[0].values)
        self.assertEqual(Decimal("0.7"), extracted.bonuses[0].percentage_point)
        self.assertEqual(extracted, ExtractedConditionsVO.model_validate_json(extracted.model_dump_json()))

    def test_타입과_범위가_틀린_조건을_거부한다(self):
        for values in ([34, 19], [True, 34], [19, 150], ["19", 34]):
            with self.subTest(values=values):
                invalid = answer()
                invalid["eligibility"]["conditions"][0]["values"] = values
                with self.assertRaises(ValidationError):
                    ExtractedConditionsVO.model_validate(invalid)

    def test_없는_근거와_과도한_금리를_거부한다(self):
        invalid = answer()
        invalid["eligibility"]["conditions"][0]["source_text"] = "누구나 가입"
        with self.assertRaises(ValueError):
            ExtractedConditionsVO.model_validate(invalid).verify(source())
        invalid = answer()
        invalid["bonuses"][0]["percentage_point"] = "0.8"
        with self.assertRaises(ValueError):
            ExtractedConditionsVO.model_validate(invalid).verify(source())

    def test_복합조건의_OR를_유지한다(self):
        combined = answer()
        first = combined["eligibility"]["conditions"][0]
        second = deepcopy(first)
        second.update(field="customer_type", operator="eq", values=["individual"])
        combined["eligibility"]["conditions"] = [{"match": "any", "conditions": [first, second]}]
        extracted = ExtractedConditionsVO.model_validate(combined)
        extracted.verify(source())

        condition = extracted.eligibility.conditions[0]
        assert isinstance(condition, ConditionGroupVO)
        self.assertEqual("any", condition.match)
        self.assertEqual(2, len(extracted.eligibility.predicates()))

    def test_가입제한이_있는데_추출이_비면_확인_필요다(self):
        empty = answer()
        empty["eligibility"]["conditions"] = []
        self.assertTrue(ExtractedConditionsVO.model_validate(empty).needs_review(source()))

    def test_원문과_규칙버전이_같은_완료만_건너뛴다(self):
        original = source()
        record = SavingCondition(
            product_id=original.product_id, source_hash=original.source_hash(),
            schema_version=CONDITION_SCHEMA_VERSION, status=ConditionStatus.EXTRACTED,
        )
        self.assertTrue(record.can_skip(original))
        for change in (
            {"join_member": "만 20~34세 개인"}, {"etc_note": "1인 1계좌"},
            {"monthly_limit": 300000}, {"max_bonus_point": Decimal("0.5")},
        ):
            with self.subTest(change=change):
                self.assertFalse(record.can_skip(original.model_copy(update=change)))
        self.assertFalse(SavingCondition.pending(original).can_skip(original))
        record.status = ConditionStatus.FAILED
        self.assertFalse(record.can_skip(original))
        record.status = ConditionStatus.EXTRACTED
        record.schema_version = "old"
        self.assertFalse(record.can_skip(original))
