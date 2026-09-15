from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from dependency_injector import providers, containers

from app.source.banks_source import BanksSource
from app.source.questions_source import QuestionsSource
from app.source.saving_products_source import SavingProductsSource
from infra.cache.banks import BanksCache
from infra.cache.questions import QuestionsCache
from infra.cache.saving_products import SavingProductsCache

if TYPE_CHECKING:
    from bootstrap.context import Context
    from bootstrap.config_base import AppConfig


class InfraConfig(containers.DeclarativeContainer):
    """판정 재료를 캐시로 줄지 매번 DB 에서 줄지 고른다. 조회 자체는 store 의 서비스가 한다."""

    store: ClassVar[providers.DependenciesContainer] = providers.DependenciesContainer()
    context: ClassVar[providers.Provider[Context[AppConfig]]] = providers.Provider()

    # 캐시를 쓸지 매번 DB 를 읽을지 CACHE_ENABLED 로 고른다. 부르는 쪽은 어느 쪽인지 모른다.
    _cache_key: ClassVar[providers.Provider[str]] = providers.Callable(
        lambda enabled: "cached" if enabled else "direct",
        context.provided.app_config.CACHE_ENABLED,
    )

    saving_products_source: ClassVar[providers.Provider[SavingProductsSource]] = providers.Selector(
        _cache_key,
        cached=providers.Singleton(
            SavingProductsCache,
            origin=store.saving_service,
            logger=context.provided.logger,
        ),
        direct=store.saving_service,
    )
    banks_source: ClassVar[providers.Provider[BanksSource]] = providers.Selector(
        _cache_key,
        cached=providers.Singleton(
            BanksCache,
            origin=store.bank_service,
            logger=context.provided.logger,
        ),
        direct=store.bank_service,
    )
    questions_source: ClassVar[providers.Provider[QuestionsSource]] = providers.Selector(
        _cache_key,
        cached=providers.Singleton(
            QuestionsCache,
            origin=store.question_service,
            logger=context.provided.logger,
        ),
        direct=store.question_service,
    )
