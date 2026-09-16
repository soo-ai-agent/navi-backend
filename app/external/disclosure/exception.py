from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from httpx import Response


class DisclosureApiError(Exception):
    """공시 호출이 실패한 경우. 오류 코드별 뜻은 docs/external-data-sources.md 오류 코드 표."""

    def __init__(self, error_code: str, error_message: str) -> None:
        super().__init__(f"금감원 API 오류 {error_code}: {error_message}")

    @classmethod
    def from_response(cls, response: Response) -> DisclosureApiError:
        """HTTP 자체가 실패한 경우 — 공시는 정상이면 200 만 준다."""
        # API 오류코드와 같은 문자열 계약으로 HTTP 상태코드를 전달한다.
        return cls(str(response.status_code), response.text[:300])
