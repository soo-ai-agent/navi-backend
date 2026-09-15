from __future__ import annotations

from dependency_injector import providers, containers
from typing_extensions import ClassVar

from app.dao.bank import BankDao
from app.dao.question import QuestionDao
from app.dao.saving import SavingDao
from app.dao.user_wish import UserWishDao


class DaoConfig(containers.DeclarativeContainer):
    bank_dao: ClassVar[providers.Provider[BankDao]] = providers.Singleton(BankDao)
    saving_dao: ClassVar[providers.Provider[SavingDao]] = providers.Singleton(
        SavingDao
    )
    question_dao: ClassVar[providers.Provider[QuestionDao]] = providers.Singleton(QuestionDao)
    user_wish_dao: ClassVar[providers.Provider[UserWishDao]] = providers.Singleton(UserWishDao)
