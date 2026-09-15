from __future__ import annotations

import os
from logging import Logger
from typing import ClassVar, Self

from pydantic import BaseModel

_DATA_DIR: str = os.environ.get("DATA_DIR", os.path.join(os.getcwd(), 'data'))

APP_NAME: str = "backend"
INI_FILE: str = "backend.ini"


class BaseAppConfig(BaseModel):
    BASE_DIR: str = ""
    DEV: bool = False
    TEST: bool = False

    @classmethod
    def from_environment(cls, **kwargs: str) -> Self:
        for name in cls.model_fields:
            if name in os.environ and name not in kwargs:
                kwargs[name] = os.environ[name]
        return cls.model_validate(kwargs)


class CommonSetting:
    @classmethod
    def print_settings(cls, logger: Logger, obj: BaseAppConfig) -> None:
        # 인증키는 로그에 남기지 않는다 — 로그 파일이 유출되면 키도 함께 나간다
        exclude = {"TEST", "DEV", "DISCLOSURE_AUTH_KEY", "LLM_API_KEY"}

        if not obj.DEV and not obj.TEST:
            exclude.add("DATABASE_URL")
        logger.info("Settings %s", obj.model_dump_json(indent=4, exclude=exclude))


class AppConfig(BaseAppConfig, CommonSetting):
    APP_NAME: ClassVar[str] = "Backend"

    LOG_LEVEL: str | None = "info"  # None이면 Uvicorn이 기존 로거의 레벨을 덮어쓰지 않는다.

    HOST: str = "localhost"
    PORT: int = 8000
    WORKERS: int = 8
    RELOAD: bool = False

    DATA_DIR: str = ""

    DATABASE_SQLITE_FILENAME: str = "backend.db"
    DATABASE_URL: str = ""

    BACKUP_DIR: str = ""
    """상품 갱신 전 sqlite 백업을 두는 곳. 비우면 ~/backups/navi-backend — 저장소 밖에 보관한다"""

    DISCLOSURE_AUTH_KEY: str = ""
    """금감원 오픈API 인증키 — 발급: docs/external-data-sources.md 참고"""

    DISCLOSURE_BASE_URL: str = ""
    """금감원 오픈API 주소. 문서에는 http 로 적혀 있으나 실제로는 https 로 307 리다이렉트된다"""

    DISCLOSURE_BANK_GROUP_CODE: str = ""
    """권역 코드 — 은행. 코드 표는 docs/external-data-sources.md 참고"""

    CACHE_ENABLED: bool = True
    """
    판정 재료(상품·은행·질문)를 캐시로 공급할지. 끄면 요청마다 DB 를 다시 읽는다.

    갱신이 즉시 보여야 하거나 캐시 문제를 의심할 때 끈다 — 컨테이너가 공급자를 바꿔 끼운다.
    """

    LLM_BASE_URL: str = ""
    """업스테이지 솔라 주소. OpenAI 호환 규격이라 요청·응답 모양이 같다"""

    LLM_API_KEY: str = ""

    LLM_MODEL: str = "solar-pro4"

    @classmethod
    def create(cls, logger: Logger, **kwargs: str) -> AppConfig:
        obj: AppConfig = cls.from_environment(**kwargs)

        if obj.DATA_DIR == "":
            obj.DATA_DIR = kwargs.get("DATA_DIR", _DATA_DIR)

        if not os.path.exists(obj.DATA_DIR):
            os.makedirs(obj.DATA_DIR, exist_ok=True)
            logger.warning(f"{obj.DATA_DIR} not exists. created")

        if "DATABASE_URL" not in kwargs and obj.DATABASE_URL == "":
            obj.DATABASE_URL = ''.join(
                ['sqlite+aiosqlite:///', os.path.join(obj.DATA_DIR, obj.DATABASE_SQLITE_FILENAME)]
            )

        if obj.BACKUP_DIR == "":
            obj.BACKUP_DIR = os.path.join("~", "backups", "navi-backend")
        obj.BACKUP_DIR = os.path.expanduser(obj.BACKUP_DIR)

        cls.print_settings(logger, obj)

        return obj
