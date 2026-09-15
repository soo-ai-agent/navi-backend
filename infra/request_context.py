from __future__ import annotations

from contextvars import ContextVar
from uuid import uuid4

_request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


def begin_request_id() -> str:
    """HTTP 요청 시작 시 새 request_id 를 발급해 문맥에 담는다. 미들웨어만 부른다."""
    request_id: str = uuid4().hex
    _request_id_var.set(request_id)
    return request_id


def current_request_id() -> str:
    """문맥의 request_id. HTTP 밖(배치·스크립트)에서는 첫 호출 때 발급해 유지한다."""
    request_id: str | None = _request_id_var.get()
    if request_id is None:
        request_id = uuid4().hex
        _request_id_var.set(request_id)
    return request_id


def short_request_id(request_id: str | None = None) -> str:
    """로그 표기용 앞 8자. 전체 값(32자)은 X-Request-Id 헤더·내부 전달에만 쓴다."""
    return (request_id or current_request_id())[:8]
