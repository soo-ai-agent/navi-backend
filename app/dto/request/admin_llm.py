from __future__ import annotations
from pydantic import BaseModel, ConfigDict, Field, StrictStr


class ConditionLlmTestRequestDTO(BaseModel):
    model_config = ConfigDict(frozen=True)
    product_id: StrictStr = Field(min_length=1, max_length=64, description="공시 원문을 가진 상품 id (은행코드:상품코드)")

class WishParseLlmTestRequestDTO(BaseModel):
    model_config = ConfigDict(frozen=True)
    message: StrictStr = Field(min_length=1, max_length=1000, description="구조화할 사용자 문장")

class WishRankLlmTestRequestDTO(BaseModel):
    model_config = ConfigDict(frozen=True)
    message: StrictStr = Field(min_length=1, max_length=4000, description="순위 근거로 쓸 사용자 상황 문장")
    # 동적 질문 키를 가진 JSON 객체이므로 이 HTTP 경계에서만 dict를 사용한다 (기존 /wishes 계약과 동일).
    answers: dict[str, StrictStr] = Field(default_factory=dict, description="지금까지 쌓인 답 전체")

class WishReplyLlmTestRequestDTO(BaseModel):
    model_config = ConfigDict(frozen=True)
    # 동적 질문 키를 가진 JSON 객체이므로 이 HTTP 경계에서만 dict를 사용한다 (기존 /wishes 계약과 동일).
    answers: dict[str, StrictStr] = Field(default_factory=dict, description="지금까지 쌓인 답 전체")
