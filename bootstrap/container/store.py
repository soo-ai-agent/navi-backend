from __future__ import annotations
from typing import ClassVar
from dependency_injector import providers, containers
from app.service.bank.bank import BankService
from app.service.question.question import QuestionService
from app.service.saving.saving import SavingService
from app.service.wish.wish import WishService


class StoreConfig(containers.DeclarativeContainer):
    """저장소를 읽고 쓰는 서비스. 트랜잭션 경계를 소유해 공급자보다 먼저 조립된다."""

    component: ClassVar[providers.DependenciesContainer] = providers.DependenciesContainer()
    dao: ClassVar[providers.DependenciesContainer] = providers.DependenciesContainer()

    bank_service: ClassVar[providers.Provider[BankService]] = providers.Singleton(
        BankService,
        async_session_maker=component.async_session_maker,
        bank_dao=dao.bank_dao,
    )
    saving_service: ClassVar[providers.Provider[SavingService]] = providers.Singleton(
        SavingService,
        async_session_maker=component.async_session_maker,
        saving_dao=dao.saving_dao,
    )
    question_service: ClassVar[providers.Provider[QuestionService]] = providers.Singleton(
        QuestionService,
        async_session_maker=component.async_session_maker,
        question_dao=dao.question_dao,
    )
    wish_service: ClassVar[providers.Provider[WishService]] = providers.Singleton(
        WishService,
        async_session_maker=component.async_session_maker,
        user_wish_dao=dao.user_wish_dao,
    )
