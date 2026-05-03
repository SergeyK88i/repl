from __future__ import annotations

from typing import Protocol

from shared.contracts.llm import (
    LlmChatRequest,
    LlmChatResponse,
    LlmEmbeddingRequest,
    LlmEmbeddingResponse,
)


class LlmPort(Protocol):
    async def chat(self, request: LlmChatRequest) -> LlmChatResponse:
        raise NotImplementedError

    async def embed(self, request: LlmEmbeddingRequest) -> LlmEmbeddingResponse:
        raise NotImplementedError


class LlmProviderError(RuntimeError):
    pass


class LlmAuthenticationError(LlmProviderError):
    pass


class LlmMalformedResponseError(LlmProviderError):
    pass
