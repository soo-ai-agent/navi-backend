from __future__ import annotations
from decimal import Decimal
from unittest import TestCase
from app.enums.answer_value import AnswerStatus
from app.enums.saving_comparison import MaturityEstimateStatus, SavingEligibilityStatus
from app.enums.saving import InterestCalcType
from app.model.database.saving import Saving
from app.model.vo.maturity_estimate_vo import MaturityEstimateVO
from app.model.vo.monthly_deposit_vo import MonthlyDepositVO
from test.service.saving.saving_fixture import answers, bonus, predicate, saving


class TestMaturityEstimate(TestCase):
    def test_단리는_매월초_납입한_세전_만기액을_원단위로_계산한다(self) -> None:
        target: Saving = saving(base="3.7")

        estimate: MaturityEstimateVO = MaturityEstimateVO.from_saving(
            target, target.rate_options[0], MonthlyDepositVO(AnswerStatus.PROVIDED, 300000),
            Decimal("3.7"), SavingEligibilityStatus.ELIGIBLE,
        )

        self.assertEqual((3600000, 72150, 3672150), (
            estimate.principal, estimate.interest_before_tax, estimate.maturity_before_tax,
        ))

    def test_최대금리_만기액은_우대조건을_모두_충족했을_때로_계산한다(self) -> None:
        target: Saving = saving(bonuses=(bonus(predicate()),), base="3.7", maximum="5.7")

        estimate: MaturityEstimateVO = MaturityEstimateVO.from_saving(
            target, target.rate_options[0], MonthlyDepositVO(AnswerStatus.PROVIDED, 300000),
            Decimal("3.7"), SavingEligibilityStatus.ELIGIBLE,
        )

        self.assertGreater(estimate.maturity_at_max_rate, estimate.maturity_before_tax)

    def test_월복리는_이전달_이자에도_이자가_붙는다(self) -> None:
        target: Saving = saving(term=2, base="12")
        target.rate_options[0].interest_calc_type = InterestCalcType.COMPOUND

        estimate: MaturityEstimateVO = MaturityEstimateVO.from_saving(
            target, target.rate_options[0], MonthlyDepositVO(AnswerStatus.PROVIDED, 10000),
            Decimal("12"), SavingEligibilityStatus.ELIGIBLE,
        )

        self.assertEqual(20301, estimate.maturity_before_tax)

    def test_금리가_0이면_원금만_돌려준다(self) -> None:
        for interest_type in InterestCalcType:
            with self.subTest(interest_type=interest_type):
                target: Saving = saving(base="0")
                target.rate_options[0].interest_calc_type = interest_type

                estimate: MaturityEstimateVO = MaturityEstimateVO.from_saving(
                    target, target.rate_options[0], MonthlyDepositVO(AnswerStatus.PROVIDED, 10000),
                    Decimal(0), SavingEligibilityStatus.ELIGIBLE,
                )

                self.assertEqual(120000, estimate.maturity_before_tax)

    def test_미응답과_잘못된_납입액을_상태로_구분한다(self) -> None:
        for value, expected in (
            ("", MaturityEstimateStatus.AMOUNT_REQUIRED),
            ("none", MaturityEstimateStatus.AMOUNT_REQUIRED),
            ("0", MaturityEstimateStatus.INVALID_AMOUNT),
            ("-1", MaturityEstimateStatus.INVALID_AMOUNT),
            ("12.5", MaturityEstimateStatus.INVALID_AMOUNT),
            ("abc", MaturityEstimateStatus.INVALID_AMOUNT),
        ):
            with self.subTest(value=value):
                target: Saving = saving()
                deposit: MonthlyDepositVO = MonthlyDepositVO.from_answers(answers(("monthly", value)))

                estimate: MaturityEstimateVO = MaturityEstimateVO.from_saving(
                    target, target.rate_options[0], deposit, Decimal("3"), SavingEligibilityStatus.ELIGIBLE,
                )

                self.assertIs(expected, estimate.status)
                self.assertEqual(0, estimate.maturity_before_tax)

    def test_특수_납입_상품은_월납입_예상액을_만들지_않는다(self) -> None:
        for name, note in (
            ("26주적금", "매주 증액 납입"),
            ("한달적금", "가입기간: 31일, 1일 1회 입금"),
            ("월복리적금", "분기당 300만원까지 납입"),
        ):
            with self.subTest(name=name):
                target: Saving = saving()
                target.name = name
                target.etc_note = note

                estimate: MaturityEstimateVO = MaturityEstimateVO.from_saving(
                    target, target.rate_options[0], MonthlyDepositVO(AnswerStatus.PROVIDED, 300000),
                    Decimal("3"), SavingEligibilityStatus.ELIGIBLE,
                )

                self.assertIs(MaturityEstimateStatus.CHECK_REQUIRED, estimate.status)

    def test_JSON_안전정수_범위_밖_금액은_표시하지_않는다(self) -> None:
        for monthly in (9007199254740992, 800000000000000):
            with self.subTest(monthly=monthly):
                target: Saving = saving()
                target.monthly_limit = None  # 기존 DB의 월 납입 한도 없음 상태를 재현한다.

                estimate: MaturityEstimateVO = MaturityEstimateVO.from_saving(
                    target, target.rate_options[0], MonthlyDepositVO(AnswerStatus.PROVIDED, monthly),
                    Decimal("3"), SavingEligibilityStatus.ELIGIBLE,
                )

                self.assertIs(MaturityEstimateStatus.CHECK_REQUIRED, estimate.status)
                self.assertEqual((0, 0, 0, 0), (
                    estimate.monthly_deposit, estimate.principal,
                    estimate.interest_before_tax, estimate.maturity_before_tax,
                ))
