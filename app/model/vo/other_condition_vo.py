from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class OtherConditionVO(BaseModel):
    """판정 필드로 표현할 수 없는 값을 사용자 체크리스트로만 보관한다."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    value: str = Field(min_length=1, max_length=10000)
    reason: str = Field(min_length=1, max_length=1000)
