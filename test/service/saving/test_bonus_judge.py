from __future__ import annotations
from decimal import Decimal
from unittest import TestCase
from app.enums.saving_condition import ConditionField as F, ConditionOperator as O, ConditionMatch as M
from app.enums.saving import BonusResult as R
from app.model.vo.checked_bonus_vo import CheckedBonusVO
from app.model.vo.saving_rate import SavingRate
from test.service.saving.saving_fixture import answers, bonus, group, predicate, saving


class TestConditionEvaluation(TestCase):
    def evaluate(self, condition, submitted):
        target = saving()
        return condition.evaluate(submitted, target.condition_context(target.rate_options[0]))

    def test_나이_범위는_양끝을_포함한다(self):
        condition = predicate(F.AGE, O.BETWEEN, (19, 34))
        for age in (19, 34):
            with self.subTest(age=age):
                self.assertIs(R.ELIGIBLE, self.evaluate(condition, answers(("age", str(age)))))
        self.assertIs(R.NOT_ELIGIBLE, self.evaluate(condition, answers(("age", "35"))))

    def test_숫자_연산자를_판정한다(self):
        for operator, value, expected in ((O.EQ, 20, R.ELIGIBLE), (O.NE, 20, R.NOT_ELIGIBLE),
                                           (O.GTE, 19, R.NOT_ELIGIBLE), (O.LTE, 19, R.ELIGIBLE)):
            with self.subTest(operator=operator):
                self.assertIs(expected, self.evaluate(predicate(F.AGE, operator, (20,)), answers(("age", str(value)))))

    def test_미응답과_건너뜀은_모름이다(self):
        for submitted in (answers(), answers(("age", "none"))):
            with self.subTest(submitted=submitted):
                self.assertIs(R.UNKNOWN, self.evaluate(predicate(), submitted))

    def test_잘못된_숫자는_모름이다(self):
        for value in ("문자", "-1", "121", "1.5", "9" * 5000, "²"):
            with self.subTest(value=value[:20]):
                self.assertIs(R.UNKNOWN, self.evaluate(predicate(), answers(("age", value))))

    def test_AND에서_하나라도_실패하면_실패한다(self):
        self.assertIs(R.NOT_ELIGIBLE, self.evaluate(group(predicate(), predicate(F.MOBILE, O.EQ, (True,))),
                                                  answers(("age", "18"))))

    def test_AND는_모든_조건을_충족해야_한다(self):
        condition = group(predicate(), predicate(F.MOBILE, O.EQ, (True,)))
        self.assertIs(R.UNKNOWN, self.evaluate(condition, answers(("age", "20"))))
        self.assertIs(R.ELIGIBLE, self.evaluate(condition, answers(("age", "20"), ("mobile", "yes"))))

    def test_OR는_하나를_충족하면_다른_답을_묻지_않는다(self):
        condition = group(predicate(), predicate(F.MOBILE, O.EQ, (True,)), match=M.ANY)
        target = saving()
        submitted = answers(("age", "20"))
        self.assertIs(R.ELIGIBLE, self.evaluate(condition, submitted))
        self.assertEqual((), condition.unanswered(submitted, target.condition_context(target.rate_options[0])))

    def test_중첩_AND_OR의_관계를_보존한다(self):
        condition = group(predicate(), group(predicate(F.MOBILE, O.EQ, (True,)),
                                             predicate(F.MARKETING, O.EQ, (True,)), match=M.ANY))
        self.assertIs(R.ELIGIBLE, self.evaluate(condition, answers(("age", "20"), ("marketing", "yes"))))

    def test_고른_은행_목록에_이_상품의_은행이_있어야_충족이다(self):
        condition = predicate(F.SALARY_BANK, O.EQ, ("PRODUCT_BANK",))
        self.assertIs(R.NOT_ELIGIBLE, self.evaluate(condition, answers(("salary_bank", "other,third"))))
        self.assertIs(R.ELIGIBLE, self.evaluate(condition, answers(("salary_bank", "other,bank"))))

    def test_기존_거래없음은_고른_은행_목록에_없어야_충족이다(self):
        condition = predicate(F.EXISTING_BANK, O.NE, ("PRODUCT_BANK",))
        self.assertIs(R.NOT_ELIGIBLE, self.evaluate(condition, answers(("existing_bank", "bank"))))
        self.assertIs(R.ELIGIBLE, self.evaluate(condition, answers(("existing_bank", "other"))))

    def test_해당_은행이_없다고_답하면_은행_조건은_미충족이다(self):
        condition = predicate(F.SALARY_BANK, O.EQ, ("PRODUCT_BANK",))
        self.assertIs(R.NOT_ELIGIBLE, self.evaluate(condition, answers(("salary_bank", "no_bank"))))

    def test_카드사용액도_해당_은행의_금액으로_판정한다(self):
        condition = predicate(F.CARD_SPEND, O.GTE, (100000,))
        self.assertIs(R.NOT_ELIGIBLE, self.evaluate(condition, answers(("card_spend_at_product_bank:bank", "50000"))))

    def test_고객_구분은_지원하는_값만_판정한다(self):
        condition = predicate(F.CUSTOMER_TYPE, O.EQ, ("individual",))
        self.assertIs(R.ELIGIBLE, self.evaluate(condition, answers(("customer_type", "individual"))))
        self.assertIs(R.UNKNOWN, self.evaluate(condition, answers(("customer_type", "other"))))

    def test_납입액은_상품_월한도를_반영한다(self):
        self.assertIs(R.NOT_ELIGIBLE, self.evaluate(predicate(F.MONTHLY_DEPOSIT, O.GTE, (600000,)),
                                                  answers(("monthly", "1000000"))))

    def test_기간은_사용자_any_답_대신_현재_옵션으로_판정한다(self):
        self.assertIs(R.ELIGIBLE, self.evaluate(predicate(F.SAVING_TERM, O.EQ, (12,)), answers(("months", "none"))))

    def test_우대_합은_공시_상한을_넘지_않는다(self):
        target = saving(bonuses=(bonus(predicate(), point="0.8"),), maximum="3.8")
        checked = (CheckedBonusVO(bonus(predicate(), point="1"), R.ELIGIBLE),)
        rate = SavingRate(target, target.rate_options[0], checked)
        self.assertEqual(Decimal("3.8"), rate.rate)

    def test_모르는_우대는_현재금리에_더하지_않는다(self):
        target = saving(bonuses=(bonus(predicate()),))
        rate = SavingRate(target, target.rate_options[0], (CheckedBonusVO(bonus(predicate()), R.UNKNOWN),))
        self.assertEqual(Decimal("3"), rate.rate)
        self.assertEqual(Decimal("3.7"), rate.possible_rate)
