from decimal import Decimal
from unittest import TestCase

from app.enums.saving_comparison import MaturityEstimateStatus, SavingEligibilityStatus
from app.enums.saving_condition import ConditionField, ConditionOperator, ConditionStatus
from app.enums.saving import InterestCalcType, ReserveType
from app.model.database.saving import Saving
from app.model.database.saving_condition import SavingCondition
from app.model.database.rate_option import RateOption
from app.model.vo.answers_vo import AnswersVO
from app.model.vo.monthly_deposit_vo import MonthlyDepositVO
from app.model.vo.saving_option_comparison_vo import SavingOptionComparisonVO
from app.model.vo.condition_bonus_vo import ConditionBonusVO
from app.model.vo.extracted_conditions_vo import ExtractedConditionsVO
from app.model.vo.other_condition_vo import OtherConditionVO
from test.service.saving.saving_fixture import answers, bonus, group, predicate, saving


def compare(target: Saving, submitted: AnswersVO) -> SavingOptionComparisonVO:
    return compare_all(target, submitted)[0]


def compare_all(target: Saving, submitted: AnswersVO) -> tuple[SavingOptionComparisonVO, ...]:
    """상품의 모든 기간을 비교한다. 비교 API 가 상품 하나를 다루는 방식과 같다."""
    deposit: MonthlyDepositVO = MonthlyDepositVO.from_answers(submitted)
    extracted = target.verified_conditions()

    compared: list[SavingOptionComparisonVO] = []
    for option in target.rate_options:
        compared.append(SavingOptionComparisonVO.evaluate(target, option, extracted, submitted, deposit))
    return tuple(compared)


class TestSavingComparison(TestCase):
    def test_월한도를_넘겨_답해도_가입할_수_있다(self) -> None:
        for monthly in ("500000", "500001"):
            with self.subTest(monthly=monthly):
                comparison: SavingOptionComparisonVO = compare(saving(), answers(("monthly", monthly)))

                self.assertIs(SavingEligibilityStatus.ELIGIBLE, comparison.eligibility.status)

    def test_월한도를_넘기면_한도까지_넣는_것으로_계산한다(self) -> None:
        comparison: SavingOptionComparisonVO = compare(saving(), answers(("monthly", "500001")))

        self.assertIs(MaturityEstimateStatus.MONTHLY_LIMIT_EXCEEDED, comparison.estimate.status)
        self.assertEqual(500000, comparison.estimate.monthly_deposit)

    def test_한도까지_계산한_만기액에는_원금과_이자가_담긴다(self) -> None:
        comparison: SavingOptionComparisonVO = compare(saving(), answers(("monthly", "500001")))

        self.assertEqual(6000000, comparison.estimate.principal)
        self.assertGreater(comparison.estimate.maturity_before_tax, comparison.estimate.principal)

    def test_일납입_한도를_월납입_한도로_단정해_가입불가로_표시하지_않는다(self) -> None:
        target: Saving = saving(monthly_limit=5000)
        target.name = "31일적금"
        extracted: ExtractedConditionsVO = ExtractedConditionsVO(eligibility=group(), bonuses=(), unresolved=())
        target.condition = SavingCondition.record(
            target.condition_source(), ConditionStatus.EXTRACTED, extracted.model_dump_json(), "",
        )

        comparison: SavingOptionComparisonVO = compare(target, answers(("monthly", "300000")))

        self.assertIs(SavingEligibilityStatus.NEEDS_CONFIRMATION, comparison.eligibility.status)
        self.assertIs(MaturityEstimateStatus.CHECK_REQUIRED, comparison.estimate.status)

    def test_특수납입_상품도_나이_미충족은_가입불가로_표시한다(self) -> None:
        target: Saving = saving(eligibility=group(predicate()))
        target.name = "31일적금"
        extracted: ExtractedConditionsVO = ExtractedConditionsVO(eligibility=group(predicate()), bonuses=(), unresolved=())
        target.condition = SavingCondition.record(
            target.condition_source(), ConditionStatus.EXTRACTED, extracted.model_dump_json(), "",
        )

        comparison: SavingOptionComparisonVO = compare(target, answers(("monthly", "300000"), ("age", "18")))

        self.assertIs(SavingEligibilityStatus.NOT_ELIGIBLE, comparison.eligibility.status)

    def test_특수납입_상품에_월예산_답변으로_금액_우대를_확정하지_않는다(self) -> None:
        monthly_bonus: ConditionBonusVO = bonus(predicate(ConditionField.MONTHLY_DEPOSIT, ConditionOperator.GTE, (100000,)))
        target: Saving = saving(bonuses=(monthly_bonus,))
        target.name = "31일적금"
        extracted: ExtractedConditionsVO = ExtractedConditionsVO(eligibility=group(), bonuses=(monthly_bonus,), unresolved=())
        target.condition = SavingCondition.record(
            target.condition_source(), ConditionStatus.EXTRACTED, extracted.model_dump_json(), "",
        )

        comparison: SavingOptionComparisonVO = compare(target, answers(("monthly", "300000")))

        self.assertEqual(Decimal("3"), comparison.applied_rate)

    def test_나이_미충족은_가입불가이다(self) -> None:
        target: Saving = saving(eligibility=group(predicate()))

        comparison: SavingOptionComparisonVO = compare(target, answers(("monthly", "300000"), ("age", "18")))

        self.assertIs(SavingEligibilityStatus.NOT_ELIGIBLE, comparison.eligibility.status)
        self.assertIs(MaturityEstimateStatus.INELIGIBLE, comparison.estimate.status)

    def test_나이_미응답은_가입조건_확인필요이다(self) -> None:
        target: Saving = saving(eligibility=group(predicate()))

        comparison: SavingOptionComparisonVO = compare(target, answers(("monthly", "300000")))

        self.assertIs(SavingEligibilityStatus.NEEDS_CONFIRMATION, comparison.eligibility.status)

    def test_자격_체크리스트를_가입가능으로_단정하지_않는다(self) -> None:
        target: Saving = saving()
        extracted: ExtractedConditionsVO = ExtractedConditionsVO(
            eligibility=group(), bonuses=(), unresolved=(),
            other_eligibility_conditions=(OtherConditionVO(
                name="별도 가입자격", value="테스트 조건", reason="은행 확인 필요",
            ),),
        )
        target.condition = SavingCondition.record(
            target.condition_source(), ConditionStatus.EXTRACTED, extracted.model_dump_json(), "",
        )

        comparison: SavingOptionComparisonVO = compare(target, answers(("monthly", "300000")))

        self.assertIs(SavingEligibilityStatus.NEEDS_CONFIRMATION, comparison.eligibility.status)
        self.assertIn("별도 가입자격: 테스트 조건", comparison.eligibility.reasons)

    def test_미검증_조건은_기본금리만_반영한다(self) -> None:
        target: Saving = saving(bonuses=(bonus(predicate()),))
        target.condition = SavingCondition.record(target.condition_source(), ConditionStatus.FAILED, "", "추출 실패")

        comparison: SavingOptionComparisonVO = compare(target, answers(("monthly", "300000"), ("age", "25")))

        self.assertIs(SavingEligibilityStatus.NEEDS_CONFIRMATION, comparison.eligibility.status)
        self.assertEqual(Decimal("3"), comparison.applied_rate)

    def test_확인된_우대만_각_옵션의_공시_상한까지_반영한다(self) -> None:
        target: Saving = saving(bonuses=(bonus(predicate(ConditionField.MOBILE, ConditionOperator.EQ, (True,))),))
        target.rate_options.append(RateOption(
            saving_term_months=12, reserve_type=ReserveType.FIXED, interest_calc_type=InterestCalcType.SIMPLE,
            base_rate=Decimal("3"), max_rate=Decimal("3.2"),
        ))
        submitted: AnswersVO = answers(("monthly", "300000"), ("mobile", "yes"))

        compared: tuple[SavingOptionComparisonVO, ...] = compare_all(target, submitted)

        self.assertEqual((Decimal("3.7"), Decimal("3.2")), tuple(option.applied_rate for option in compared))

    def test_우대_미응답을_최고금리로_가정하지_않는다(self) -> None:
        target: Saving = saving(bonuses=(bonus(predicate()),))

        comparison: SavingOptionComparisonVO = compare(target, answers(("monthly", "300000")))

        self.assertEqual(Decimal("3"), comparison.applied_rate)
