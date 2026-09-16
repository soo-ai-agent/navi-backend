from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN
from typing import assert_never
from app.enums.answer_value import AnswerStatus
from app.enums.saving_comparison import MaturityEstimateStatus, SavingEligibilityStatus
from app.enums.saving import InterestCalcType
from app.model.database.saving import Saving
from app.model.database.rate_option import RateOption
from app.model.vo.monthly_deposit_vo import MonthlyDepositVO
from app.model.vo.monthly_limit_vo import MonthlyLimitVO

MAX_SAFE_JSON_INTEGER = 2 ** 53 - 1
MONTHS_PER_YEAR = 12
PERCENT_DIVISOR = 100


@dataclass(frozen=True)
class MaturityEstimateVO:
    status: MaturityEstimateStatus
    monthly_deposit: int
    principal: int
    interest_before_tax: int
    maturity_before_tax: int
    maturity_at_max_rate: int
    """우대조건을 모두 충족했을 때의 세전 만기액. 화면이 '최대 얼마'와 '내 기준 얼마'를 나란히 보여준다."""
    reason: str
    """추정하지 못한 상태에서는 모든 금액이 0이며 화면은 status와 reason을 표시한다."""

    @classmethod
    def from_saving(
            cls, saving: Saving, option: RateOption, deposit: MonthlyDepositVO,
            applied_rate: Decimal, eligibility_status: SavingEligibilityStatus,
    ) -> MaturityEstimateVO:
        blocked: MaturityEstimateVO | None = cls._blocking_reason(saving, option, deposit, eligibility_status)
        if blocked is not None:
            return blocked

        limit: MonthlyLimitVO = MonthlyLimitVO.from_database(saving.monthly_limit)
        # 한도를 넘으면 계산을 포기하지 않고 한도까지 넣는 것으로 보여 준다.
        limited: bool = deposit.exceeds(limit)
        monthly_deposit: int = limit.amount if limited else deposit.amount

        return cls._estimate(option, monthly_deposit, applied_rate, limited, limit)

    @classmethod
    def _blocking_reason(
            cls, saving: Saving, option: RateOption, deposit: MonthlyDepositVO,
            eligibility_status: SavingEligibilityStatus,
    ) -> MaturityEstimateVO | None:
        """계산을 막는 사유. 없으면 None 을 돌려줘 계산을 이어 가게 한다."""
        if deposit.status is AnswerStatus.UNANSWERED:
            return cls.unavailable(MaturityEstimateStatus.AMOUNT_REQUIRED, "월 납입액을 입력하면 예상 만기금액을 계산합니다.")

        if deposit.status is AnswerStatus.INVALID:
            return cls.unavailable(MaturityEstimateStatus.INVALID_AMOUNT, "월 납입액은 0보다 큰 정수로 입력해 주세요.")

        if deposit.amount > MAX_SAFE_JSON_INTEGER:
            return cls.unavailable(MaturityEstimateStatus.CHECK_REQUIRED, "입력 금액이 정확하게 계산할 수 있는 범위를 초과했습니다.")

        if eligibility_status is SavingEligibilityStatus.NOT_ELIGIBLE:
            return cls.unavailable(MaturityEstimateStatus.INELIGIBLE, "입력한 답변으로는 가입 자격을 충족하지 않아 예상액을 계산하지 않습니다.")

        if cls.has_special_payment_terms(saving):
            return cls.unavailable(MaturityEstimateStatus.CHECK_REQUIRED, "")

        if option.saving_term_months <= 0:
            return cls.unavailable(MaturityEstimateStatus.CHECK_REQUIRED, "공시된 가입기간을 확인해야 합니다.")

        return None

    @classmethod
    def _estimate(
            cls, option: RateOption, monthly_deposit: int, applied_rate: Decimal,
            limited: bool, limit: MonthlyLimitVO,
    ) -> MaturityEstimateVO:
        principal: int = monthly_deposit * option.saving_term_months

        interest: Decimal = cls._interest(monthly_deposit, option, applied_rate)
        # 금액은 세전 이자를 원 단위로 절사한 뒤 JSON 정수로 한 번 변환한다.
        interest_before_tax: int = int(interest.to_integral_value(rounding=ROUND_DOWN))
        maturity_before_tax: int = principal + interest_before_tax

        max_interest: Decimal = cls._interest(monthly_deposit, option, option.max_rate)
        maturity_at_max_rate: int = principal + int(max_interest.to_integral_value(rounding=ROUND_DOWN))

        if maturity_at_max_rate > MAX_SAFE_JSON_INTEGER:
            return cls.unavailable(MaturityEstimateStatus.CHECK_REQUIRED, "예상 금액이 정확하게 표시할 수 있는 범위를 초과했습니다.")

        if limited:
            return cls(
                MaturityEstimateStatus.MONTHLY_LIMIT_EXCEEDED, monthly_deposit, principal,
                interest_before_tax, maturity_before_tax, maturity_at_max_rate,
                f"이 상품의 월 한도 {limit.amount:,}원까지 넣는 것으로 계산했습니다.",
            )

        return cls(
            MaturityEstimateStatus.ESTIMATED, monthly_deposit, principal,
            interest_before_tax, maturity_before_tax, maturity_at_max_rate,
            cls._calculation_note(option),
        )

    @staticmethod
    def _calculation_note(option: RateOption) -> str:
        if option.interest_calc_type is InterestCalcType.COMPOUND:
            return "월복리를 가정했습니다."
        return ""

    @classmethod
    def unavailable(cls, status: MaturityEstimateStatus, reason: str) -> MaturityEstimateVO:
        return cls(status, 0, 0, 0, 0, 0, reason)

    @staticmethod
    def has_special_payment_terms(saving: Saving) -> bool:
        payment_text: str = (saving.name + saving.etc_note).replace(" ", "").replace("\n", "")
        # ponytail: 공시 원문에 드러난 특수 납입만 보수적으로 막는다. 납입 일정이 구조화되면 그 값으로 대체한다.
        special_terms: tuple[str, ...] = ("매일", "매주", "일납", "주납", "26주", "31일", "1일1회", "초입금일", "분기", "증액")
        return any(term in payment_text for term in special_terms)

    @staticmethod
    def _interest(monthly_deposit: int, option: RateOption, applied_rate: Decimal) -> Decimal:
        months: int = option.saving_term_months
        match option.interest_calc_type:
            case InterestCalcType.SIMPLE:
                return monthly_deposit * applied_rate * months * (months + 1) / (2 * PERCENT_DIVISOR * MONTHS_PER_YEAR)
            case InterestCalcType.COMPOUND:
                monthly_rate: Decimal = applied_rate / PERCENT_DIVISOR / MONTHS_PER_YEAR
                balance: Decimal = Decimal(0)
                for _month in range(months):
                    balance = (balance + monthly_deposit) * (1 + monthly_rate)
                return balance - monthly_deposit * months
            case _:
                assert_never(option.interest_calc_type)
