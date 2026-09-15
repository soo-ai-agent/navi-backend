from datetime import date
from unittest import TestCase

from app.enums.saving import InterestCalcType, JoinRestriction, ReserveType
from app.external import disclosure


def _raw_saving(**overrides) -> disclosure.SavingProduct:
    values = {
        "dcls_month": "202608", "fin_co_no": "0010001", "fin_prdt_cd": "WR0001F",
        "kor_co_nm": "우리은행", "fin_prdt_nm": "우리SUPER주거래적금", "join_way": "영업점,인터넷",
        "join_member": "실명의 개인", "join_deny": "1", "spcl_cnd": "급여이체 연 0.7%p",
        "mtrt_int": "만기 후 50%", "etc_note": "-", "max_limit": 500000, "dcls_strt_day": "20260820",
    }
    return disclosure.SavingProduct(**{**values, **overrides})


def _raw_option(**overrides) -> disclosure.SavingProductOption:
    values = {
        "fin_co_no": "0010001", "fin_prdt_cd": "WR0001F", "save_trm": "12",
        "rsrv_type": "F", "intr_rate_type": "S", "intr_rate": 2.45, "intr_rate2": 3.85,
    }
    return disclosure.SavingProductOption(**{**values, **overrides})


class TestToSaving(TestCase):
    def test_은행코드와_상품코드를_합쳐_식별자를_만든다(self):
        saving = _raw_saving().to_saving()

        self.assertEqual("0010001:WR0001F", saving.product_id)

    def test_문자열로_온_값의_타입을_확정한다(self):
        saving = _raw_saving().to_saving()

        self.assertEqual(JoinRestriction.ANYONE, saving.join_restriction)
        self.assertEqual("2026-08", saving.disclosure_month)
        self.assertEqual(date(2026, 8, 20), saving.disclosure_start_date)

    def test_한도없음을_뜻하는_숫자는_비운다(self):
        saving = _raw_saving(max_limit=999999999).to_saving()

        self.assertIsNone(saving.monthly_limit)

    def test_상품명에_섞인_개행을_편다(self):
        saving = _raw_saving(fin_prdt_nm="BNK내맘대로 \n적금").to_saving()

        self.assertEqual("BNK내맘대로 적금", saving.name)

    def test_없음으로_온_우대조건은_빈_문자열이_된다(self):
        saving = _raw_saving(spcl_cnd="해당없음").to_saving()

        self.assertEqual('', saving.bonus_condition_text)

    def test_우대조건_원문이_같으면_해시도_같다(self):
        first = _raw_saving(spcl_cnd="급여이체 연 0.7%p").to_saving()
        second = _raw_saving(spcl_cnd="급여이체 연 0.7%p").to_saving()
        changed = _raw_saving(spcl_cnd="급여이체 연 0.8%p").to_saving()

        self.assertEqual(first.bonus_source_hash, second.bonus_source_hash)
        self.assertNotEqual(first.bonus_source_hash, changed.bonus_source_hash)


class TestToRateOption(TestCase):
    def test_코드를_enum_으로_바꾼다(self):
        option = _raw_option(rsrv_type="S", intr_rate_type="M").to_rate_option()

        assert option is not None
        self.assertEqual(12, option.saving_term_months)
        self.assertEqual(ReserveType.FIXED, option.reserve_type)
        self.assertEqual(InterestCalcType.COMPOUND, option.interest_calc_type)

    def test_금리가_비면_적재하지_않는다(self):
        self.assertIsNone(_raw_option(intr_rate=None).to_rate_option())


class TestToBank(TestCase):
    def test_법인_표기를_정리해_화면_이름을_만든다(self):
        company = disclosure.Company(
            fin_co_no="0013175", kor_co_nm="농협은행주식회사", homp_url=None, cal_tel=None
        )

        bank = company.to_bank()

        self.assertEqual("농협은행주식회사", bank.original_name)
        self.assertEqual("농협은행", bank.display_name)
        self.assertEqual('', bank.homepage_url)
