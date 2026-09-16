"""브라우저 연결 테스트 전용 서버. 고정 상품으로 실제 질문 API를 실행한다."""

from __future__ import annotations
import logging
from dependency_injector import providers
from fastapi import FastAPI
from unittest.mock import AsyncMock
from app.enums.saving_condition import ConditionField, ConditionOperator
from app.model.database.bank import Bank
from app.model.vo.banks_vo import BanksVO
from app.model.vo.questions_vo import QuestionsVO
from app.model.vo.saving_products_vo import SavingProductsVO
from infra.cache.banks import BanksCache
from infra.cache.questions import QuestionsCache
from infra.cache.saving_products import SavingProductsCache
from app.service.saving.saving_catalog import SavingCatalogService
from bootstrap.container.application import ApplicationConfig
from test.service.saving.saving_fixture import bonus, group, predicate, saving, question_flow
from web.controllers.api.v1 import catalog, question
from web.exception_handler import register_exception_handlers


target = saving(
    eligibility=group(predicate()),
    bonuses=(bonus(predicate(ConditionField.SALARY_BANK, ConditionOperator.EQ, ("PRODUCT_BANK",))),),
)
bank = Bank(bank_code="bank", original_name="bank", display_name="bank",
            homepage_url="https://bank.example", call_center="1588-0000")
container = ApplicationConfig()
container.service.question_flow_service.override(providers.Object(question_flow(target)))
savings_cache = AsyncMock(spec=SavingProductsCache)
savings_cache.get.return_value = SavingProductsVO(products=(target,))
banks_cache = AsyncMock(spec=BanksCache)
banks_cache.get.return_value = BanksVO(banks=(bank,))
container.infra.saving_products_source.override(providers.Object(savings_cache))
container.infra.banks_source.override(providers.Object(banks_cache))
container.service.saving_catalog_service.override(
    providers.Object(SavingCatalogService(
        savings_cache, banks_cache, logging.getLogger("test.product_catalog"),
    ))
)
container.wire(modules=(catalog, question))

app = FastAPI()
register_exception_handlers(app)
app.include_router(question.router)
app.include_router(catalog.router)
