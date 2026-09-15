from __future__ import annotations

from decimal import Decimal
from unittest import IsolatedAsyncioTestCase, TestCase

from app.dto.response.next_step import NextStepResponseDTO
from app.dto.response.ranking import RankedSavingResponseDTO
from app.enums.next_step import NextStepStatus
from app.enums.saving_condition import (
    BonusConditionStatus, ConditionField, ConditionOperator, ConditionSourceField, ConditionStatus
)
from app.enums.saving import JoinRestriction
from app.exception.condition import ConditionVerificationError
from app.model.database.saving import Saving
# 단독 실행에서도 Product의 문자열 관계가 가리키는 ORM 모델을 등록한다.
from app.model.database.saving_bonus import SavingBonus
from app.model.database.saving_condition import SavingCondition
from app.model.vo.manual_conditions_vo import ManualConditionsVO
from app.model.vo.condition_group_vo import ConditionGroupVO
from app.model.vo.condition_predicate_vo import ConditionPredicateVO
from app.model.vo.extracted_conditions_vo import ExtractedConditionsVO
from app.model.vo.other_condition_vo import OtherConditionVO
from app.model.vo.saving_condition_source_vo import SavingConditionSourceVO
from app.service.question.question_flow import QuestionFlowService
from test.service.saving.saving_fixture import answers, group, saving, question_flow


def checklist_conditions(eligibility: ConditionGroupVO) -> ExtractedConditionsVO:
    return ExtractedConditionsVO(
        eligibility=eligibility, bonuses=(), unresolved=(), bonus_status=BonusConditionStatus.CHECKLIST,
        other_eligibility_conditions=(OtherConditionVO(
            name="거주지", value="지정 지역 거주자", reason="가입 시 거주지 증빙을 확인해야 합니다.",
        ),),
        other_bonus_conditions=(OtherConditionVO(
            name="적금 자동이체", value="적금 자동이체 6회 이상이면 연 1.0%p",
            reason="적금 납입 횟수를 확인해야 합니다.",
        ),),
    )


def checklist_saving(eligibility: ConditionGroupVO) -> Saving:
    target: Saving = saving()
    target.join_member = "지정 지역 거주자"
    target.join_restriction = JoinRestriction.PARTIAL
    target.etc_note = "만 19세 이상, 월 1만원 이상 납입"
    target.bonus_condition_text = "적금 자동이체 6회 이상이면 연 1.0%p"
    target.rate_options[0].max_rate = Decimal("4")
    target.condition = SavingCondition.from_manual(target.condition_source(), checklist_conditions(eligibility))
    return target


class TestManualConditionFlow(IsolatedAsyncioTestCase):
    async def test_체크리스트만_있는_제한가입_상품도_기간선택후_추천한다(self) -> None:
        flow: QuestionFlowService = question_flow(checklist_saving(group()))

        first: NextStepResponseDTO = await flow.next_step(answers())
        assert first.question is not None
        result: NextStepResponseDTO = await flow.next_step(answers((first.question.key, "12")))

        self.assertEqual(NextStepStatus.DONE, result.status)
        assert result.result is not None
        self.assertEqual(("bank:P1",), tuple(row.product_id for row in result.result.rows))

    async def test_미판정_우대금리는_추천금리에_포함하지_않는다(self) -> None:
        flow: QuestionFlowService = question_flow(checklist_saving(group()))

        step: NextStepResponseDTO = await flow.next_step(answers(("months", "12")))

        assert step.result is not None
        self.assertEqual(Decimal("3"), step.result.rows[0].rate)
        self.assertEqual((), step.result.rows[0].bonus_results)

    async def test_자격과_우대체크리스트를_분리해_반환한다(self) -> None:
        flow: QuestionFlowService = question_flow(checklist_saving(group()))

        step: NextStepResponseDTO = await flow.next_step(answers(("months", "12")))

        assert step.result is not None
        row: RankedSavingResponseDTO = step.result.rows[0]
        self.assertEqual(
            ("지정 지역 거주자",), tuple(item.value for item in row.other_eligibility_conditions),
        )
        self.assertEqual(
            ("적금 자동이체 6회 이상이면 연 1.0%p",), tuple(item.value for item in row.other_bonus_conditions),
        )
        self.assertEqual((), row.other_conditions)

    async def test_체크리스트가_있어도_가입나이_미달은_추천에서_제외한다(self) -> None:
        eligibility: ConditionGroupVO = group(ConditionPredicateVO(
            field=ConditionField.AGE, operator=ConditionOperator.GTE, values=(19,),
            source_field=ConditionSourceField.NOTE, source_text="만 19세 이상",
        ))
        flow: QuestionFlowService = question_flow(checklist_saving(eligibility))

        for age, expected_count in (("18", 0), ("19", 1)):
            with self.subTest(age=age):
                step: NextStepResponseDTO = await flow.next_step(answers(("months", "12"), ("age", age)))

                assert step.result is not None
                self.assertEqual(expected_count, len(step.result.rows))

    async def test_체크리스트가_있어도_월최저납입액_미달은_추천에서_제외한다(self) -> None:
        eligibility: ConditionGroupVO = group(ConditionPredicateVO(
            field=ConditionField.MONTHLY_DEPOSIT, operator=ConditionOperator.GTE, values=(10000,),
            source_field=ConditionSourceField.NOTE, source_text="월 1만원 이상 납입",
        ))
        flow: QuestionFlowService = question_flow(checklist_saving(eligibility))

        for monthly, expected_count in (("9999", 0), ("10000", 1)):
            with self.subTest(monthly=monthly):
                step: NextStepResponseDTO = await flow.next_step(answers(("months", "12"), ("monthly", monthly)))

                assert step.result is not None
                self.assertEqual(expected_count, len(step.result.rows))


class TestManualConditionVerification(TestCase):
    def test_직접작성한_조건은_작성경위와_함께_추출완료로_보존한다(self) -> None:
        source: SavingConditionSourceVO = checklist_saving(group()).condition_source()
        extracted: ExtractedConditionsVO = checklist_conditions(group())

        record: SavingCondition = SavingCondition.from_manual(source, extracted)

        self.assertEqual(ConditionStatus.EXTRACTED, record.status)
        self.assertIn("직접 작성(Codex)", record.review_reason)
        self.assertEqual(extracted, record.read_verified(source))

    def test_체크리스트_종류에_맞지_않거나_없는_근거를_거부한다(self) -> None:
        source: SavingConditionSourceVO = checklist_saving(group()).condition_source()
        extracted: ExtractedConditionsVO = checklist_conditions(group())

        for field, value in (
            ("other_eligibility_conditions", source.spcl_cnd),
            ("other_bonus_conditions", source.join_member),
            ("other_eligibility_conditions", "원문에 없는 자격조건"),
            ("other_bonus_conditions", "원문에 없는 우대조건"),
        ):
            with self.subTest(field=field, value=value):
                invalid: ExtractedConditionsVO = extracted.model_copy(update={field: (
                    OtherConditionVO(name="확인 항목", value=value, reason="은행에서 확인해야 합니다."),
                )})

                with self.assertRaises(ConditionVerificationError):
                    SavingCondition.from_manual(source, invalid)

    def test_유의사항_원문도_자격과_우대체크리스트의_근거로_인정한다(self) -> None:
        source: SavingConditionSourceVO = checklist_saving(group()).condition_source().model_copy(update={
            "etc_note": "거주지 증빙 필요, 계약기간별 자동이체 횟수 확인",
            "join_restriction": JoinRestriction.ANYONE,
        })
        extracted: ExtractedConditionsVO = checklist_conditions(group()).model_copy(update={
            "other_eligibility_conditions": (OtherConditionVO(
                name="거주지 증빙", value="거주지 증빙 필요", reason="증빙 서류를 확인해야 합니다.",
            ),),
            "other_bonus_conditions": (OtherConditionVO(
                name="자동이체 횟수", value="계약기간별 자동이체 횟수 확인", reason="납입 이력을 확인해야 합니다.",
            ),),
        })

        record: SavingCondition = SavingCondition.from_manual(source, extracted)

        self.assertEqual(extracted, record.read_verified(source))

    def test_가입대상_일부만_보존한_체크리스트로_검토를_생략하지_않는다(self) -> None:
        source: SavingConditionSourceVO = checklist_saving(group()).condition_source()
        extracted: ExtractedConditionsVO = checklist_conditions(group()).model_copy(update={
            "other_eligibility_conditions": (OtherConditionVO(
                name="거주지", value="지역 거주자", reason="거주지를 확인해야 합니다.",
            ),),
        })

        with self.assertRaises(ValueError):
            SavingCondition.from_manual(source, extracted)

    def test_체크리스트_상태에_우대원문이_없으면_거부한다(self) -> None:
        source: SavingConditionSourceVO = checklist_saving(group()).condition_source()
        extracted: ExtractedConditionsVO = checklist_conditions(group())

        for entries in ((), (OtherConditionVO(name="빈 우대", value=" ", reason="원문 없음"),)):
            with self.subTest(entries=entries):
                invalid: ExtractedConditionsVO = extracted.model_copy(update={"other_bonus_conditions": entries})

                with self.assertRaises(ConditionVerificationError):
                    SavingCondition.from_manual(source, invalid)

    def test_UNKNOWN_응답은_전체_공시_체크리스트로_보존한다(self) -> None:
        source: SavingConditionSourceVO = checklist_saving(group()).condition_source()
        extracted: ExtractedConditionsVO = checklist_conditions(group()).model_copy(update={
            "bonus_status": BonusConditionStatus.UNKNOWN,
        })

        record: SavingCondition = SavingCondition.from_extracted(source, extracted)

        self.assertEqual(ExtractedConditionsVO.from_source_checklist(source), record.read_verified(source))

    def test_가입대상_원문이_없으면_체크리스트로_검토를_생략하지_않는다(self) -> None:
        source: SavingConditionSourceVO = checklist_saving(group()).condition_source().model_copy(update={
            "join_member": "",
        })

        record: SavingCondition = SavingCondition.from_checklist(source, "원문 확인 필요")

        self.assertEqual(ConditionStatus.NEEDS_REVIEW, record.status)

    def test_우대원문이_없는데_금리차이가_있으면_검토가_필요하다(self) -> None:
        source: SavingConditionSourceVO = checklist_saving(group()).condition_source().model_copy(update={
            "spcl_cnd": "",
        })

        record: SavingCondition = SavingCondition.from_checklist(source, "원문 확인 필요")

        self.assertEqual(ConditionStatus.NEEDS_REVIEW, record.status)

    def test_우대금리없음과_우대체크리스트가_함께_있으면_거부한다(self) -> None:
        source: SavingConditionSourceVO = checklist_saving(group()).condition_source().model_copy(update={
            "spcl_cnd": "없음", "max_bonus_point": Decimal("0"),
        })
        extracted: ExtractedConditionsVO = checklist_conditions(group()).model_copy(update={
            "bonus_status": BonusConditionStatus.NO_BONUS,
            "other_bonus_conditions": (OtherConditionVO(name="우대", value="없음", reason="확인 필요"),),
        })

        with self.assertRaises(ConditionVerificationError):
            SavingCondition.from_manual(source, extracted)

    def test_검토한_상품이나_원문이_다르면_직접작성한_조건을_거부한다(self) -> None:
        source: SavingConditionSourceVO = checklist_saving(group()).condition_source()
        manual: ManualConditionsVO = ManualConditionsVO(
            product_id=source.product_id, source_hash=source.source_hash(), conditions=checklist_conditions(group()),
        )

        for candidate, current_source in (
            (manual.model_copy(update={"product_id": "bank:OTHER"}), source),
            (manual, source.model_copy(update={"etc_note": "변경된 공시 원문"})),
        ):
            with self.subTest(product_id=candidate.product_id, source_hash=current_source.source_hash()):
                with self.assertRaises(ValueError):
                    candidate.verify_source(current_source)
