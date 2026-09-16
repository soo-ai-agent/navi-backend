from __future__ import annotations
import logging
from importlib import import_module
from os.path import dirname
from dotenv import load_dotenv
from bootstrap.config_base import AppConfig, INI_FILE, APP_NAME

LOG_FORMAT = "%(levelname)-8s %(asctime)s %(message)s"
"""레벨명은 8자 고정 폭 — INFO·WARNING 길이 차이로 뒤 열이 밀리지 않게 한다."""
formatter = logging.Formatter(LOG_FORMAT)
stream_handler = logging.StreamHandler()
logging.basicConfig(handlers=(stream_handler,), level=logging.INFO, format=LOG_FORMAT)
# httpx 요청 URL에는 인증 쿼리 값이 포함될 수 있으므로 원문 URL을 로그에 남기지 않는다.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

logger = logging.getLogger("app")
# logger.setLevel(logging.INFO)


if load_dotenv(INI_FILE):
    logger.info(f"Initializing {APP_NAME} environment")

app_config = AppConfig.create(
    BASE_DIR=dirname(__file__),
    logger=logger
)

try:
    import_module("config_after")
except ModuleNotFoundError:
    pass
