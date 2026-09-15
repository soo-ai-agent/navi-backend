from __future__ import annotations

import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from infra.request_context import current_request_id, short_request_id
from app.exception.question import SavingConditionsUnavailableError
from app.exception.saving import SavingBackupError, SavingNotFoundError
from app.exception.wish import WishStructureError

logger = logging.getLogger("app.web")


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(SavingNotFoundError)
    async def handle_saving_not_found(request: Request, error: SavingNotFoundError) -> JSONResponse:
        logger.warning("요청 실패 | req=%s | path=%s | status=404 | 사유=%s", short_request_id(), request.url.path, error)
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(error)}
        )

    @app.exception_handler(SavingBackupError)
    async def handle_backup_failed(request: Request, error: SavingBackupError) -> JSONResponse:
        logger.warning("요청 실패 | req=%s | path=%s | status=503 | 사유=%s", short_request_id(), request.url.path, error)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content={"detail": str(error)}
        )

    @app.exception_handler(SavingConditionsUnavailableError)
    async def handle_conditions_unavailable(
            request: Request, error: SavingConditionsUnavailableError
    ) -> JSONResponse:
        logger.warning("요청 실패 | req=%s | path=%s | status=503 | 사유=%s", short_request_id(), request.url.path, error)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content={"detail": str(error)}
        )

    @app.exception_handler(WishStructureError)
    async def handle_wish_structure_failed(request: Request, error: WishStructureError) -> JSONResponse:
        logger.warning("요청 실패 | req=%s | path=%s | status=502 | 사유=%s", short_request_id(), request.url.path, error)
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY, content={"detail": str(error)}
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, error: Exception) -> JSONResponse:
        logger.exception("요청 처리 실패 | req=%s | path=%s | status=500 | 오류=%s", short_request_id(), request.url.path, type(error).__name__)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "요청을 처리하지 못했습니다."},
        )
