from __future__ import annotations
from typing import Any
from pydantic import BaseModel, ConfigDict


class LlmTestResponseDTO(BaseModel):
    """LLM 단건 시험 실행 결과. 관리자가 프롬프트·원시응답·파싱 결과를 눈으로 대조한다."""

    model_config = ConfigDict(frozen=True)

    prompt: str
    """실제 사용된 시스템 프롬프트 전문"""

    user_content: str
    """LLM 에게 user 역할로 넘긴 재료 전문"""

    raw_response: str
    """LLM 이 돌려준 원문 그대로"""

    # 네 LLM 의 구조화 결과 모양이 제각각이라 이 시험 경계에서만 Any 를 허용한다.
    parsed: Any | None = None
    """구조화(검증) 결과. 검증에 실패하면 null 이고 parse_error 에 사유가 실린다"""

    parse_error: str | None = None
    """검증 실패 사유. 성공하면 null"""
