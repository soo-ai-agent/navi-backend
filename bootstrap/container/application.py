from __future__ import annotations

from typing import TYPE_CHECKING

from dependency_injector import providers, containers
from typing_extensions import ClassVar

from bootstrap.container.component import ComponentConfig
from bootstrap.container.dao import DaoConfig
from bootstrap.container.infra import InfraConfig
from bootstrap.container.service import ServiceConfig
from bootstrap.container.store import StoreConfig

if TYPE_CHECKING:
    from bootstrap.context import Context
    from bootstrap.config_base import AppConfig


class ApplicationConfig(containers.DeclarativeContainer):
    context: ClassVar[providers.Provider[Context[AppConfig]]] = providers.Provider()

    component: ClassVar[providers.Container[ComponentConfig]] = providers.Container(
        ComponentConfig,
        context=context,
    )
    dao: ClassVar[providers.Container[DaoConfig]] = providers.Container(
        DaoConfig,
    )
    store: ClassVar[providers.Container[StoreConfig]] = providers.Container(
        StoreConfig,
        component=component,
        dao=dao,
    )
    infra: ClassVar[providers.Container[InfraConfig]] = providers.Container(
        InfraConfig,
        context=context,
        store=store,
    )
    service: ClassVar[providers.Container[ServiceConfig]] = providers.Container(
        ServiceConfig,
        context=context,
        component=component,
        store=store,
        infra=infra,
    )
