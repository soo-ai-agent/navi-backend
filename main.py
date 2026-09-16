from __future__ import annotations
from contextlib import asynccontextmanager
from time import perf_counter
from typing import AsyncIterator
from fastapi import FastAPI, Request, Response
from bootstrap.container.application import ApplicationConfig
from bootstrap.context import Context
from bootstrap.initializer import DevelopEnvDbInitializer
from config import app_config, logger as _logger
from infra.request_context import begin_request_id, short_request_id
from web.controllers.api.v1 import catalog, question, wish
from web.controllers.api.v1.admin import saving as admin_saving
from web.exception_handler import register_exception_handlers

di_container = ApplicationConfig()
context = Context(di_container, _logger, app_config=app_config)
di_container.wire(modules=(catalog, question, admin_saving, wish))


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await DevelopEnvDbInitializer(di_container)()
    # 첫 사용자가 DB 적재를 기다리지 않도록 미리 채운다 (4왕복 6.5ms → 1.2ms)
    await di_container.infra.saving_products_source().get()
    await di_container.infra.banks_source().get()
    await di_container.infra.questions_source().get()
    yield


app = FastAPI(title=app_config.APP_NAME, lifespan=lifespan)
register_exception_handlers(app)


@app.middleware("http")
async def log_request(request: Request, call_next) -> Response:
    # proxy_headers=True 라 프록시 뒤에서도 request.client 가 실제 클라이언트 IP 다.
    request_id: str = begin_request_id()
    ip: str = request.client.host if request.client else "unknown"
    started_at: float = perf_counter()
    _logger.info("요청 시작 | req=%s | ip=%s | method=%s | path=%s", short_request_id(request_id), ip, request.method, request.url.path)

    response: Response = await call_next(request)

    response.headers["X-Request-Id"] = request_id
    _logger.info(
        "요청 종료 | req=%s | status=%d | 소요_ms=%.1f",
        short_request_id(request_id), response.status_code, (perf_counter() - started_at) * 1000,
    )
    return response


app.include_router(question.router)
app.include_router(admin_saving.router)
app.include_router(catalog.router)
app.include_router(wish.router)

if __name__ == "__main__":
    import uvicorn
    from uvicorn.config import LOGGING_CONFIG

    from config import LOG_FORMAT

    uvicorn_log_config: dict = LOGGING_CONFIG
    for formatter_name in ("default", "access"):
        uvicorn_log_config["formatters"][formatter_name]["fmt"] = LOG_FORMAT
    uvicorn.run(
        'main:app',
        host=app_config.HOST,
        port=app_config.PORT,
        workers=app_config.WORKERS,
        log_level=app_config.LOG_LEVEL,
        log_config=uvicorn_log_config,
        # 요청 시작·종료는 위 미들웨어가 req 와 함께 남긴다 — uvicorn access 로그는 중복이라 끈다.
        access_log=False,
        reload=app_config.RELOAD,
        proxy_headers=True,
    )
