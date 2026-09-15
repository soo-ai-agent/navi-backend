from __future__ import annotations

from typing import Sequence

from app.enums.answer_kind import AnswerKind
from app.enums.judge_kind import JudgeKind
from app.model.database.question import Question

SEED_QUESTIONS: Sequence[Question] = (
    # 순위를 매기기 전에 받는 질문 — 무엇을 비교할지 정한다
    Question(code="months", title="얼마 동안 넣을까요?",
             answer_kind=AnswerKind.OPTIONS, judge_kind=JudgeKind.SAVING_TERM, ask_order=1),
    Question(code="monthly", title="매달 얼마씩 넣을까요? (원)",
             answer_kind=AnswerKind.NUMBER, judge_kind=JudgeKind.MONTHLY, ask_order=2),

    # 우대조건 판정에 쓰는 질문 — LLM 이 원문을 이 judge_kind 로 분류하면 여기로 묶인다
    Question(code="age", title="나이가 어떻게 되세요? (만)",
             answer_kind=AnswerKind.NUMBER, judge_kind=JudgeKind.AGE),
    Question(code="existingBank", title="예금이나 적금을 이미 갖고 있는 은행이 있나요?",
             answer_kind=AnswerKind.OPTIONS, judge_kind=JudgeKind.FIRST, inverted=True),
    Question(code="salaryBank", title="급여나 연금은 어느 은행으로 받으세요?",
             answer_kind=AnswerKind.OPTIONS, judge_kind=JudgeKind.SALARY),
    Question(code="cardBank", title="신용·체크카드는 주로 어느 은행 것을 쓰세요?",
             answer_kind=AnswerKind.OPTIONS, judge_kind=JudgeKind.CARD),
    Question(code="autopay", title="공과금을 자동이체로 내고 계세요?",
             answer_kind=AnswerKind.BOOLEAN, judge_kind=JudgeKind.AUTOPAY),
    Question(code="mobile", title="인터넷이나 앱으로 가입하실 수 있으세요?",
             answer_kind=AnswerKind.BOOLEAN, judge_kind=JudgeKind.MOBILE),
    Question(code="principal", title="만기까지 모을 금액은 얼마쯤인가요? (원)",
             answer_kind=AnswerKind.NUMBER, judge_kind=JudgeKind.PRINCIPAL),
    Question(code="marketing", title="마케팅 정보 수신에 동의하실 수 있나요?",
             answer_kind=AnswerKind.BOOLEAN, judge_kind=JudgeKind.MARKETING),
    Question(code="performanceMonths", title="우대조건 실적을 몇 개월 채울 수 있으세요?",
             answer_kind=AnswerKind.NUMBER, judge_kind=JudgeKind.PERFORMANCE_MONTHS),
    Question(code="paymentAccountBank", title="급여·자동이체·카드결제의 출금계좌는 어느 은행인가요?",
             answer_kind=AnswerKind.OPTIONS, judge_kind=JudgeKind.PAYMENT_ACCOUNT),
)
"""
공시와 무관하게 늘 쓰는 질문들. 적재 배치가 없으면 넣고, 있으면 DB 값을 건드리지 않는다 —
운영에서 고친 문구를 배치가 되돌리지 않게 한다.

RANDOM 과 OTHER 는 시드에 없다. 자동 판정할 수 없는 조건은 추출 결과에 보존한다.
"""
