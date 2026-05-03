from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


LlmRole = Literal["system", "user", "assistant", "function", "tool"]


class LlmMessage(BaseModel):
    role: LlmRole
    content: str
    name: str | None = None


class LlmFunctionDefinition(BaseModel):
    name: str
    description: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)


class LlmFunctionCall(BaseModel):
    name: str
    arguments: dict[str, Any] | str | None = None


class LlmUsage(BaseModel):
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


class LlmChatRequest(BaseModel):
    messages: list[LlmMessage]
    model: str | None = None
    temperature: float = 0.3
    top_p: float = 0.8
    max_tokens: int = 1024
    repetition_penalty: float | None = 1.07
    functions: list[LlmFunctionDefinition] = Field(default_factory=list)
    function_call: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class LlmChatResponse(BaseModel):
    content: str | None = None
    function_call: LlmFunctionCall | None = None
    usage: LlmUsage | None = None
    model: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class LlmEmbeddingRequest(BaseModel):
    text: str
    model: str | None = None


class LlmEmbeddingResponse(BaseModel):
    embedding: list[float]
    model: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)
