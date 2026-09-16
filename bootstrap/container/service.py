from __future__ import annotations
from typing import TYPE_CHECKING, ClassVar
from dependency_injector import providers, containers
from app.external.disclosure import DisclosureClient
from app.external.llm import LlmClient
from app.service.question.question_flow import QuestionFlowService
from app.service.saving.bonus_structure import BonusStructureService
from app.external.llm.condition_parser import ConditionLlmParser
from app.service.saving.disclosure_sync import DisclosureSyncService
from app.service.saving.saving_catalog import SavingCatalogService
from app.service.saving.saving_refresh import SavingRefreshService
from app.service.saving.raw_saving import RawSavingService
from app.external.llm.wish_parser import WishLlmParser
from app.external.llm.wish_ranker import WishLlmRanker
from app.external.llm.wish_reply_writer import WishReplyWriter
from app.service.wish.wish_ranking import WishRankingService
from app.service.wish.wish_structure import WishStructureService

if TYPE_CHECKING:
    from bootstrap.context import Context
    from bootstrap.config_base import AppConfig


class ServiceConfig(containers.DeclarativeContainer):
    component: ClassVar[providers.DependenciesContainer] = providers.DependenciesContainer()
    store: ClassVar[providers.DependenciesContainer] = providers.DependenciesContainer()
    infra: ClassVar[providers.DependenciesContainer] = providers.DependenciesContainer()
    context: ClassVar[providers.Provider[Context[AppConfig]]] = providers.Provider()
    disclosure_client: ClassVar[providers.Provider[DisclosureClient]] = providers.Singleton(
        DisclosureClient,
        base_url=context.provided.app_config.DISCLOSURE_BASE_URL,
        bank_group_code=context.provided.app_config.DISCLOSURE_BANK_GROUP_CODE,
        auth_key=context.provided.app_config.DISCLOSURE_AUTH_KEY,
        logger=context.provided.logger,
    )
    llm_client: ClassVar[providers.Provider[LlmClient]] = providers.Singleton(
        LlmClient,
        base_url=context.provided.app_config.LLM_BASE_URL,
        api_key=context.provided.app_config.LLM_API_KEY,
        model=context.provided.app_config.LLM_MODEL,
        logger=context.provided.logger,
    )
    raw_saving_service: ClassVar[providers.Provider[RawSavingService]] = providers.Singleton(
        RawSavingService,
        disclosure_client=disclosure_client,
    )
    disclosure_sync_service: ClassVar[providers.Provider[DisclosureSyncService]] = providers.Singleton(
        DisclosureSyncService,
        disclosure_client=disclosure_client,
        saving_service=store.saving_service,
        bank_service=store.bank_service,
        logger=context.provided.logger,
    )
    condition_llm_parser: ClassVar[providers.Provider[ConditionLlmParser]] = providers.Singleton(
        ConditionLlmParser,
        llm_client=llm_client,
    )
    bonus_structure_service: ClassVar[providers.Provider[BonusStructureService]] = providers.Singleton(
        BonusStructureService,
        saving_service=store.saving_service,
        question_service=store.question_service,
        condition_llm_parser=condition_llm_parser,
        logger=context.provided.logger,
    )
    saving_refresh_service: ClassVar[providers.Provider[SavingRefreshService]] = providers.Singleton(
        SavingRefreshService,
        disclosure_sync_service=disclosure_sync_service,
        bonus_structure_service=bonus_structure_service,
        savings_source=infra.saving_products_source,
        bank_service=infra.banks_source,
        questions_service=infra.questions_source,
        db_backup=component.db_backup,
        logger=context.provided.logger,
    )
    saving_catalog_service: ClassVar[providers.Provider[SavingCatalogService]] = providers.Singleton(
        SavingCatalogService,
        savings_source=infra.saving_products_source,
        bank_service=infra.banks_source,
        logger=context.provided.logger,
    )
    question_flow_service: ClassVar[providers.Provider[QuestionFlowService]] = providers.Singleton(
        QuestionFlowService,
        savings_source=infra.saving_products_source,
        bank_service=infra.banks_source,
        questions_service=infra.questions_source,
        logger=context.provided.logger,
    )
    wish_llm_parser: ClassVar[providers.Provider[WishLlmParser]] = providers.Singleton(
        WishLlmParser,
        llm_client=llm_client,
    )
    wish_reply_writer: ClassVar[providers.Provider[WishReplyWriter]] = providers.Singleton(
        WishReplyWriter,
        llm_client=llm_client,
    )
    wish_llm_ranker: ClassVar[providers.Provider[WishLlmRanker]] = providers.Singleton(
        WishLlmRanker,
        llm_client=llm_client,
    )
    wish_ranking_service: ClassVar[providers.Provider[WishRankingService]] = providers.Singleton(
        WishRankingService,
        savings_source=infra.saving_products_source,
        banks_source=infra.banks_source,
        wish_ranker=wish_llm_ranker,
        logger=context.provided.logger,
    )
    wish_structure_service: ClassVar[providers.Provider[WishStructureService]] = providers.Singleton(
        WishStructureService,
        wish_service=store.wish_service,
        questions_source=infra.questions_source,
        question_flow_service=question_flow_service,
        wish_ranking_service=wish_ranking_service,
        wish_parser=wish_llm_parser,
        reply_writer=wish_reply_writer,
        logger=context.provided.logger,
    )
