from __future__ import annotations
from unittest import TestCase
from app.model.database.saving import Saving
from app.model.vo.saving_rate import SavingRate
from app.model.vo.saving_ranking_vo import SavingRankingVO
from test.service.saving.saving_fixture import saving


class TestSavingRanking(TestCase):
    def test_같은_상품기간의_최고금리만_남기고_동률은_원래_상품순서를_지킨다(self) -> None:
        first: Saving = saving("bank:A", base="3")
        second: Saving = saving("bank:B", base="4")
        better: Saving = saving("bank:A", base="4")
        first_rate: SavingRate = SavingRate(first, first.rate_options[0], ())
        second_rate: SavingRate = SavingRate(second, second.rate_options[0], ())
        better_rate: SavingRate = SavingRate(better, better.rate_options[0], ())

        ranking: SavingRankingVO = SavingRankingVO.from_rates((first_rate, second_rate, better_rate))

        self.assertEqual((better_rate, second_rate), ranking.rates)
