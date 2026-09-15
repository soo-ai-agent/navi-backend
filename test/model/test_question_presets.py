from unittest import TestCase

from app.dto.response.question import QuestionResponseDTO
from app.enums.answer_kind import AnswerKind
from app.enums.answer_value import AnswerStatus
from app.enums.saving_condition import ConditionField
from app.model.vo.banks_vo import BanksVO
from app.model.vo.questions_vo import QuestionsVO
from app.model.vo.saving_products_vo import SavingProductsVO
from app.model.vo.condition_answer_vo import ConditionAnswerVO
from app.model.vo.condition_context_vo import ConditionContextVO
from app.model.vo.monthly_limit_vo import MonthlyLimitVO
from test.service.saving.saving_fixture import saving


class TestQuestionPresets(TestCase):
    def test_숫자_질문은_범위가_아닌_정확한_값과_직접입력을_지원한다(self) -> None:
        for field, expected in (
            (ConditionField.AGE, ("18", "20", "30", "40", "50", "60", "none")),
            (ConditionField.MONTHLY_DEPOSIT, ("100000", "300000", "500000", "1000000", "none")),
            (ConditionField.PRINCIPAL, ("1000000", "3000000", "5000000", "10000000", "none")),
            (ConditionField.CARD_SPEND, ("0", "300000", "500000", "1000000", "none")),
        ):
            with self.subTest(field=field):
                answer: ConditionAnswerVO = ConditionAnswerVO(field, ConditionContextVO("bank", 12, MonthlyLimitVO.unlimited()))

                question: QuestionResponseDTO = QuestionResponseDTO.from_condition(answer, "은행", BanksVO(()))

                self.assertIs(AnswerKind.NUMBER_WITH_OPTIONS, question.answer_kind)
                self.assertEqual(expected, tuple(value for value, label in question.options))

    def test_숫자_질문은_모두_모르겠어요를_고를_수_있다(self) -> None:
        for field in (ConditionField.AGE, ConditionField.MONTHLY_DEPOSIT, ConditionField.PRINCIPAL,
                      ConditionField.CARD_SPEND, ConditionField.PERFORMANCE_MONTHS):
            with self.subTest(field=field):
                answer: ConditionAnswerVO = ConditionAnswerVO(field, ConditionContextVO("bank", 12, MonthlyLimitVO.unlimited()))

                question: QuestionResponseDTO = QuestionResponseDTO.from_condition(answer, "은행", BanksVO(()))

                self.assertIn(("none", "모르겠어요"), question.options)

    def test_기간_건너뛰기_선택지는_답변상태의_HTTP값을_사용한다(self) -> None:
        savings_vo: SavingProductsVO = SavingProductsVO((saving(),))
        questions_vo: QuestionsVO = QuestionsVO(())

        question: QuestionResponseDTO = QuestionResponseDTO.for_saving_terms(savings_vo, questions_vo)

        self.assertEqual((AnswerStatus.SKIPPED.value, "상관없어요"), question.options[-1])

    def test_월납입액_질문은_금액_선택지와_모르겠어요를_제공한다(self) -> None:
        savings_vo: SavingProductsVO = SavingProductsVO((saving(),))
        questions_vo: QuestionsVO = QuestionsVO(())

        question: QuestionResponseDTO = QuestionResponseDTO.for_monthly_deposit(questions_vo)

        self.assertIs(AnswerKind.NUMBER_WITH_OPTIONS, question.answer_kind)
        self.assertEqual(
            ("100000", "300000", "500000", "1000000", "none"),
            tuple(value for value, label in question.options),
        )
