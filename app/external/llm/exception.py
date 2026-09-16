from __future__ import annotations
from typing import TYPE_CHECKING
import httpx
from pydantic import ValidationError
from app.exception.condition import ConditionVerificationError

if TYPE_CHECKING:
    from httpx import Response


class LlmApiError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(f"LLM 오류: {message}")

    @classmethod
    def from_response(cls, response: Response) -> LlmApiError:
        if response.status_code in (401, 403):
            return cls("AI 서비스 인증에 실패했습니다. 관리자가 API 키와 접근 권한을 확인해야 합니다.")
        if response.status_code == 429:
            return cls("AI 서비스의 호출량 또는 사용 한도에 도달했습니다.")
        return cls(f"AI 서비스가 요청을 처리하지 못했습니다(HTTP {response.status_code}).")


class ConditionLlmParseError(Exception):
    def __init__(self, raw_response: str, cause: Exception) -> None:
        self.raw_response = raw_response
        self.cause = cause
        super().__init__(str(cause))


class ConditionExtractionError(Exception):
    """외부 응답이나 비밀값을 노출하지 않는 조건 추출 실패 안내."""

    @classmethod
    def from_error(cls, error: Exception) -> ConditionExtractionError:
        """실패 원인을 사용자·관리자가 읽을 문장으로 옮긴다. 외부 응답 본문은 싣지 않는다."""
        if isinstance(error, ConditionLlmParseError):
            return cls.from_error(error.cause)

        if isinstance(error, (httpx.TimeoutException, TimeoutError)):
            return cls("AI 응답 대기 시간을 초과해 상품 조건을 추출하지 못했습니다.")

        if isinstance(error, LlmApiError):
            return cls(str(error))

        if isinstance(error, httpx.RequestError):
            return cls("AI 서비스에 연결하지 못해 상품 조건을 추출하지 못했습니다.")

        if isinstance(error, ValidationError):
            return cls._from_validation_error(error)

        if isinstance(error, ConditionVerificationError):
            return cls(f"AI가 추출한 조건을 검증하지 못했습니다: {error}")

        if isinstance(error, ValueError):
            return cls("AI 추출 결과를 처리하는 중 값 검증에 실패했습니다. 관리자 확인이 필요합니다.")

        return cls("상품 조건 추출 중 내부 오류가 발생했습니다. 관리자 확인이 필요합니다.")

    @classmethod
    def _from_validation_error(cls, error: ValidationError) -> ConditionExtractionError:
        # Pydantic 의 오류 목록·context 는 dict 다. 입력값은 제외하고 자체 검증기가 만든 안내만 전달한다.
        issues = error.errors(include_input=False, include_url=False)

        for issue in issues:
            context = issue.get("ctx")
            if context is None:
                continue

            verification_error = context.get("error")
            if isinstance(verification_error, ConditionVerificationError):
                return cls(f"AI가 추출한 조건을 검증하지 못했습니다: {verification_error}")

        first = issues[0]
        message = str(first.get("msg", "검증 규칙을 확인할 수 없습니다"))

        location_parts: list[str] = []
        for part in first.get("loc", ()):
            location_parts.append(str(part))
        location = ".".join(location_parts)

        if location:
            return cls(f"AI 응답의 JSON 형식 또는 조건값 검증 실패: {location}: {message}")

        return cls(f"AI 응답의 JSON 형식 또는 조건값 검증 실패: {message}")
