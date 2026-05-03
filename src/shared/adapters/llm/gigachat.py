from __future__ import annotations

import asyncio
import logging
import ssl
import time
import uuid
from dataclasses import dataclass
from typing import Any

import aiohttp

from shared.contracts.llm import (
    LlmChatRequest,
    LlmChatResponse,
    LlmEmbeddingRequest,
    LlmEmbeddingResponse,
    LlmFunctionCall,
    LlmUsage,
)
from shared.ports.llm import (
    LlmAuthenticationError,
    LlmMalformedResponseError,
    LlmProviderError,
    LlmPort,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GigaChatAdapterConfig:
    auth_token: str
    scope: str = "GIGACHAT_API_PERS"
    model: str = "GigaChat"
    embeddings_model: str = "Embeddings"
    oauth_url: str = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
    chat_url: str = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
    embeddings_url: str = "https://gigachat.devices.sberbank.ru/api/v1/embeddings"
    timeout_seconds: float = 60.0
    verify_ssl: bool = True
    ca_bundle_path: str | None = None
    token_refresh_margin_seconds: int = 60


class GigaChatAdapter(LlmPort):
    def __init__(self, config: GigaChatAdapterConfig) -> None:
        self.config = config
        self._access_token: str | None = None
        self._expires_at: float | None = None
        self._token_lock = asyncio.Lock()
        self._ssl = self._build_ssl_context()

    async def chat(self, request: LlmChatRequest) -> LlmChatResponse:
        payload: dict[str, Any] = {
            "model": request.model or self.config.model,
            "messages": [message.model_dump(exclude_none=True) for message in request.messages],
            "temperature": request.temperature,
            "top_p": request.top_p,
            "n": 1,
            "stream": False,
            "max_tokens": request.max_tokens,
        }
        if request.repetition_penalty is not None:
            payload["repetition_penalty"] = request.repetition_penalty
        if request.functions:
            payload["functions"] = [
                function.model_dump(exclude_none=True) for function in request.functions
            ]
        if request.function_call:
            payload["function_call"] = request.function_call

        data = await self._post_with_bearer_retry(self.config.chat_url, payload)
        message = data.get("choices", [{}])[0].get("message", {})
        if not isinstance(message, dict):
            raise LlmMalformedResponseError("GigaChat returned malformed chat message")

        function_call = message.get("function_call")
        content = message.get("content")
        if function_call:
            return LlmChatResponse(
                function_call=LlmFunctionCall.model_validate(function_call),
                usage=self._parse_usage(data),
                model=data.get("model"),
                raw=data,
            )
        if not content:
            raise LlmMalformedResponseError("GigaChat returned an empty chat response")

        return LlmChatResponse(
            content=content,
            usage=self._parse_usage(data),
            model=data.get("model"),
            raw=data,
        )

    async def embed(self, request: LlmEmbeddingRequest) -> LlmEmbeddingResponse:
        payload = {
            "model": request.model or self.config.embeddings_model,
            "input": [request.text],
        }
        data = await self._post_with_bearer_retry(self.config.embeddings_url, payload)
        embedding = data.get("data", [{}])[0].get("embedding")
        if not isinstance(embedding, list):
            raise LlmMalformedResponseError("GigaChat returned an empty embedding response")
        return LlmEmbeddingResponse(
            embedding=embedding,
            model=data.get("model") or request.model or self.config.embeddings_model,
            raw=data,
        )

    async def _post_with_bearer_retry(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        last_error: LlmProviderError | None = None
        for attempt in range(2):
            token = await self._get_access_token()
            try:
                return await self._post_json(
                    url,
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                        "Authorization": f"Bearer {token}",
                    },
                    json_payload=payload,
                )
            except LlmAuthenticationError as exc:
                last_error = exc
                if attempt == 0:
                    await self._invalidate_access_token()
                    continue
                raise
        if last_error:
            raise last_error
        raise LlmProviderError("GigaChat request failed")

    async def _get_access_token(self) -> str:
        if self._access_token and not self._is_token_expiring():
            return self._access_token

        async with self._token_lock:
            if self._access_token and not self._is_token_expiring():
                return self._access_token
            data = await self._request_access_token()
            token = data.get("access_token")
            if not token:
                raise LlmMalformedResponseError("GigaChat OAuth response has no access_token")
            self._access_token = token
            self._expires_at = self._parse_expires_at(data.get("expires_at"))
            logger.info("GigaChat access token refreshed")
            return token

    async def _request_access_token(self) -> dict[str, Any]:
        auth_token = self.config.auth_token
        if auth_token.lower().startswith("basic "):
            auth_token = auth_token[6:]

        return await self._post_json(
            self.config.oauth_url,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
                "RqUID": str(uuid.uuid4()),
                "Authorization": f"Basic {auth_token}",
            },
            form_payload={"scope": self.config.scope},
            auth_request=True,
        )

    async def _post_json(
        self,
        url: str,
        *,
        headers: dict[str, str],
        json_payload: dict[str, Any] | None = None,
        form_payload: dict[str, Any] | None = None,
        auth_request: bool = False,
    ) -> dict[str, Any]:
        timeout = aiohttp.ClientTimeout(total=self.config.timeout_seconds)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    url,
                    headers=headers,
                    json=json_payload,
                    data=form_payload,
                    ssl=self._ssl,
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    error_text = await response.text()
                    if response.status == 401:
                        raise LlmAuthenticationError(
                            f"GigaChat authentication failed: HTTP {response.status}"
                        )
                    operation = "oauth" if auth_request else "api"
                    raise LlmProviderError(
                        f"GigaChat {operation} request failed: HTTP {response.status}: {error_text}"
                    )
        except aiohttp.ClientError as exc:
            raise LlmProviderError(f"GigaChat network error: {exc}") from exc

    async def _invalidate_access_token(self) -> None:
        async with self._token_lock:
            self._access_token = None
            self._expires_at = None

    def _is_token_expiring(self) -> bool:
        if self._expires_at is None:
            return False
        return time.time() + self.config.token_refresh_margin_seconds >= self._expires_at

    def _build_ssl_context(self) -> bool | ssl.SSLContext:
        if not self.config.verify_ssl:
            return False
        if self.config.ca_bundle_path:
            return ssl.create_default_context(cafile=self.config.ca_bundle_path)
        return True

    @staticmethod
    def _parse_expires_at(value: Any) -> float | None:
        if value is None:
            return None
        try:
            expires_at = float(value)
        except (TypeError, ValueError):
            return None
        if expires_at > 10_000_000_000:
            return expires_at / 1000
        return expires_at

    @staticmethod
    def _parse_usage(data: dict[str, Any]) -> LlmUsage | None:
        usage = data.get("usage")
        if not isinstance(usage, dict):
            return None
        return LlmUsage.model_validate(usage)
