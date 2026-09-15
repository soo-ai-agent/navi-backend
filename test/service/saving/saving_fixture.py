from __future__ import annotations

from datetime import date
import logging
from decimal import Decimal
from unittest.mock import AsyncMock

from dependency_injector import providers
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.model.database.saving_bonus  # 테스트를 단독 실행할 때도 Product의 ORM 관계를 등록한다.
from app.service.question.question_flow import QuestionFlowService
from infra.cache.banks import BanksCache
from infra.cache.questions import QuestionsCache
from infra.cache.saving_products import SavingProductsCache
from bootstrap.container.application import ApplicationConfig
from web.controllers.api.v1 import question
from web.exception_handler import register_exception_handlers

from app.constants.question_text import GOAL_AMOUNT_KEY
from app.enums.answer_value import AnswerStatus
from app.enums.saving_condition import ConditionField, ConditionMatch, ConditionOperator, ConditionSourceField, ConditionStatus
from app.enums.saving import InterestCalcType, JoinRestriction, ReserveType
from app.model.vo.banks_vo import BanksVO
from app.model.vo.questions_vo import QuestionsVO
from app.model.vo.saving_products_vo import SavingProductsVO
from app.model.vo.answer_vo import AnswerVO
from app.model.vo.answers_vo import AnswersVO
from app.model.database.bank import Bank
from app.model.database.saving import Saving
from app.model.database.saving_condition import SavingCondition
from app.model.database.rate_option import RateOption
from app.model.vo.condition_bonus_vo import ConditionBonusVO
from app.model.vo.condition_group_vo import ConditionGroupVO
from app.model.vo.condition_predicate_vo import ConditionPredicateVO
from app.model.vo.extracted_conditions_vo import ExtractedConditionsVO


MONTHLY_DEPOSIT_KEY: str = "monthly"

ALWAYS_ASKED_KEYS: tuple[str, ...] = (MONTHLY_DEPOSIT_KEY, GOAL_AMOUNT_KEY)
"""기간을 고른 뒤 흐름이 상품과 무관하게 항상 묻는 질문들."""


def raw_answers(*entries: tuple[str, str]) -> AnswersVO:
    """받은 답만 담은 답변. 상시 질문 자체를 검증할 때 쓴다."""
    return AnswersVO(tuple(AnswerVO(key, value) for key, value in entries))


def answers(*entries: tuple[str, str]) -> AnswersVO:
    """테스트 답변. 검증 대상이 아닌 상시 질문은 '모르겠어요'로 채워 그 질문에서 멈추지 않게 한다."""
    given: dict[str, str] = {key: value for key, value in entries}
    for key in ALWAYS_ASKED_KEYS:
        given.setdefault(key, AnswerStatus.SKIPPED.value)
    return raw_answers(*given.items())


def predicate(field=ConditionField.AGE, operator=ConditionOperator.GTE, values=(19,)) -> ConditionPredicateVO:
    return ConditionPredicateVO(field=field, operator=operator, values=values,
                              source_field=ConditionSourceField.JOIN_MEMBER, source_text="테스트 조건")


def group(*conditions, match=ConditionMatch.ALL) -> ConditionGroupVO:
    return ConditionGroupVO(match=match, conditions=conditions)


def bonus(*conditions, point="0.7", match=ConditionMatch.ALL) -> ConditionBonusVO:
    return ConditionBonusVO(label="우대", percentage_point=Decimal(point), condition=group(*conditions, match=match))


def saving(product_id="bank:P1", *, eligibility=None, bonuses=(), base="3", maximum="4", term=12,
            monthly_limit=500000) -> Saving:
    target = Saving(
        product_id=product_id, bank_code=product_id.split(":")[0], name="테스트 적금",
        join_member="테스트 조건", join_restriction=JoinRestriction.ANYONE,
        join_ways="앱", monthly_limit=monthly_limit, bonus_condition_text="테스트 조건" if bonuses else "",
        bonus_source_hash="source", after_maturity_rate_text="", etc_note="",
        disclosure_month="2026-09", disclosure_start_date=date(2026, 9, 1),
        rate_options=[RateOption(saving_term_months=term, reserve_type=ReserveType.FREE,
                                interest_calc_type=InterestCalcType.SIMPLE, base_rate=Decimal(base),
                                max_rate=Decimal(maximum if bonuses else base))], bonuses=[],
    )
    extracted = ExtractedConditionsVO(eligibility=group() if eligibility is None else eligibility,
                                    bonuses=bonuses, unresolved=())
    source = target.condition_source()
    extracted.verify(source)
    target.condition = SavingCondition.record(source, ConditionStatus.EXTRACTED, extracted.model_dump_json(), "")
    return target


def question_flow(*products: Saving) -> QuestionFlowService:
    savings_cache = AsyncMock(spec=SavingProductsCache)
    savings_cache.get.return_value = SavingProductsVO(products)

    banks_cache = AsyncMock(spec=BanksCache)
    banks_cache.get.return_value = BanksVO(tuple(
        Bank(bank_code=code, display_name=code) for code in sorted({p.bank_code for p in products})
    ))

    questions_cache = AsyncMock(spec=QuestionsCache)
    questions_cache.get.return_value = QuestionsVO(())

    return QuestionFlowService(
        savings_cache, banks_cache, questions_cache, logging.getLogger("test.question_flow"),
    )


def question_api(*products: Saving) -> TestClient:
    """질문 API 를 앱 전체로 호출하는 클라이언트. 도메인 예외의 상태코드 변환까지 확인할 때 쓴다."""
    container = ApplicationConfig()
    container.service.question_flow_service.override(providers.Object(question_flow(*products)))
    container.wire(modules=(question,))

    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(question.router)
    return TestClient(app)
