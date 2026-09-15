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


class ChatResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    choices: tuple[ChatChoice, ...] = Field(min_length=1)
