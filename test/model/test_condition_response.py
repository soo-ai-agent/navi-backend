from __future__ import annotations
import json
from decimal import Decimal
from unittest import TestCase
from app.enums.saving_condition import BonusConditionStatus
from app.enums.saving_condition import ConditionStatus
from app.enums.saving import JoinRestriction
from app.external.llm.condition_response import normalize_condition_response
from app.model.database.saving_condition import SavingCondition
from app.model.vo.extracted_conditions_vo import ExtractedConditionsVO
from app.model.vo.saving_condition_source_vo import SavingConditionSourceVO


def source() -> SavingConditionSourceVO:
    return SavingConditionSourceVO(
        product_id="bank:P1", name="적금", join_member="누구나",
        join_restriction=JoinRestriction.ANYONE, join_ways="앱",
        spcl_cnd="자동이체 시 0.5%p", etc_note="", monthly_limit=500000,
        saving_terms=(12,), max_bonus_point=Decimal("0.5"),
    )


class TestConditionResponse(TestCase):
    def test_모르는_조건을_AND_OR에서_삭제하여_자동판정하지_않는다(self) -> None:
        for match in ("all", "any"):
            with self.subTest(match=match):
                answer = {
                    "eligibility": {"match": match, "conditions": [
                        {"field": "age", "operator": "gte", "values": [19],
                         "source_field": "join_member", "source_text": "만 19세 이상"},
                        {"field": "residence", "operator": "eq", "values": ["부산"],
                         "source_field": "join_member", "source_text": "부산 거주자"},
                    ]},
                    "bonuses": [], "unresolved": [],
                }

                with self.assertRaisesRegex(ValueError, "정의되지 않은 조건 필드"):
                    normalize_condition_response(json.dumps(answer))

    def test_빈_복합조건을_지워_자격을_단순화하지_않는다(self) -> None:
        answer = '{"eligibility":{"match":"all","conditions":[{"match":"any","conditions":[]}]}}'

        with self.assertRaisesRegex(ValueError, "빈 복합조건"):
            normalize_condition_response(answer)

    def test_우대체크리스트_응답의_상태를_명시한다(self) -> None:
        received = ExtractedConditionsVO.model_validate_json('''{
            "eligibility":{"match":"all","conditions":[]}, "bonuses":[], "unresolved":[],
            "bonus_status":"UNKNOWN", "other_bonus_conditions":[{
                "name":"우대", "value":"자동이체 시 0.5%p", "reason":"납입 방식을 확인해야 합니다."
            }]
        }''')

        extracted = received.with_source_status(source())
        record = SavingCondition.from_extracted(source(), extracted)

        self.assertEqual(BonusConditionStatus.CHECKLIST, extracted.bonus_status)
        self.assertEqual(extracted, record.read_verified(source()))

    def test_외부_문자열_숫자와_불리언을_내부_타입으로_복원한다(self) -> None:
        answer = {
            "eligibility": {"match": "all", "conditions": [{
                "field": "monthly_deposit", "operator": "eq", "values": ["500000"],
                "source_field": "join_member", "source_text": "월 500000원",
            }]},
            "bonuses": [{
                "label": "자동이체", "percentage_point": "0.5",
                "condition": {"match": "all", "conditions": [{
                    "field": "autopay", "operator": "eq", "values": ["true"],
                    "source_field": "spcl_cnd", "source_text": "자동이체 시 0.5%p",
                }]},
            }],
            "unresolved": [],
        }

        extracted = ExtractedConditionsVO.model_validate_json(
            normalize_condition_response(json.dumps(answer))
        )

        self.assertIs(type(extracted.eligibility.predicates()[0].values[0]), int)
        self.assertIs(type(extracted.bonuses[0].condition.predicates()[0].values[0]), bool)
        self.assertEqual(BonusConditionStatus.UNKNOWN, extracted.bonus_status)

    def test_정의되지_않은_필드는_판정하지_않고_기타로_보관한다(self) -> None:
        answer = {
            "eligibility": {"match": "all", "conditions": [], "new_rule": "확인 필요"},
            "bonuses": [{
                "label": "자동이체", "percentage_point": "0.1", "future_rule": "확인",
                "condition": {"match": "all", "conditions": [{
                    "field": "autopay", "operator": "eq", "values": [True],
                    "source_field": "spcl_cnd", "source_text": "자동이체 시 0.5%p",
                }]},
            }],
            "unresolved": [], "future_field": 500000,
        }

        extracted = ExtractedConditionsVO.model_validate_json(
            normalize_condition_response(json.dumps(answer, ensure_ascii=False))
        )
        extracted.verify(source())

        self.assertEqual(1, len(extracted.other_eligibility_conditions))
        self.assertEqual(1, len(extracted.other_conditions))
        self.assertEqual(1, len(extracted.other_bonus_conditions))
        self.assertTrue(all(
            item.reason.endswith("표시 전용")
            for item in (
                extracted.other_eligibility_conditions
                + extracted.other_bonus_conditions
                + extracted.other_conditions
            )
        ))
        self.assertFalse(extracted.needs_review(source()))
        self.assertEqual(ConditionStatus.EXTRACTED, SavingCondition.from_extracted(source(), extracted).status)
