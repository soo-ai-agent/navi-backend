from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class ChatMessage(BaseModel):
    model_config = ConfigDict(frozen=True)
    role: str
    content: str


class ResponseFormat(BaseModel):
    model_config = ConfigDict(frozen=True)
    type: Literal["json_object"] = "json_object"


class ChatRequest(BaseModel):
    model_config = ConfigDict(frozen=True)
    model: str
    messages: tuple[ChatMessage, ...]
    response_format: ResponseFormat = ResponseFormat()
    reasoning_effort: str = "medium"
    max_tokens: int = 4096


class ChatChoice(BaseModel):
    model_config = ConfigDict(frozen=True)
    message: ChatMessage


class ChatUsage(BaseModel):
    model_config = ConfigDict(frozen=True)
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

    def summary(self) -> str:
        """로그 표기용 'prompt/completion/total' 한 토막."""
        return f"{self.prompt_tokens}/{self.completion_tokens}/{self.total_tokens}"


class ChatResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    choices: tuple[ChatChoice, ...] = Field(min_length=1)
    usage: ChatUsage | None = None
    """토큰 사용량. 서버·프록시에 따라 생략될 수 있어 없음을 허용한다 — 로그 메타로만 쓴다."""
