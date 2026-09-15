from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class UnmappedWishVO(BaseModel):
    """질문 목록에 대응하지 않아 원문 그대로 보존하는 요구."""

    model_config = ConfigDict(frozen=True)

    name: str
    """사용자가 바로 알아보는 짧은 이름 (예: 앱 사용 편의성)"""
    text: str
    """사용자 문장에서 그대로 잘라온 구절"""
