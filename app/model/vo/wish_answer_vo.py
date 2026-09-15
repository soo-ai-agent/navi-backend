from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class WishAnswerVO(BaseModel):
    """사용자 문장에서 읽어낸 기존 질문의 답."""

    model_config = ConfigDict(frozen=True)

    code: str
    """question.code — 질문 흐름이 답을 받는 키와 같다"""
    value: str
