from __future__ import annotations
from typing import TYPE_CHECKING, Generic, TypeVar
from dependency_injector import providers

if TYPE_CHECKING:
    from logging import Logger

    from bootstrap.container.application import ApplicationConfig

TAppConfig = TypeVar("TAppConfig")


class Context(Generic[TAppConfig]):
    """DI 컨테이너에 logger 와 app_config 를 공급하는 실행 문맥."""

    logger: Logger
    app_config: TAppConfig

    def __init__(self, di_container: ApplicationConfig, logger: Logger, app_config: TAppConfig) -> None:
        self.logger = logger
        self.app_config = app_config
        di_container.context.override(providers.Object(self))
