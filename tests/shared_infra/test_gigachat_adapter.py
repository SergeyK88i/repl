from __future__ import annotations

import asyncio
import time
import unittest
from typing import Any

from shared.adapters.llm.gigachat import GigaChatAdapter, GigaChatAdapterConfig
from shared.contracts.llm import LlmChatRequest, LlmMessage
from shared.ports.llm import LlmAuthenticationError


class FakeGigaChatAdapter(GigaChatAdapter):
    def __init__(self) -> None:
        super().__init__(
            GigaChatAdapterConfig(
                auth_token="Basic test-auth-token",
                timeout_seconds=1,
                verify_ssl=True,
            )
        )
        self.calls: list[dict[str, Any]] = []
        self.chat_failures_before_success = 0

    async def _post_json(self, url: str, **kwargs):
        self.calls.append({"url": url, **kwargs})
        if kwargs.get("auth_request"):
            return {
                "access_token": f"access-token-{len(self.calls)}",
                "expires_at": time.time() + 3600,
            }
        if self.chat_failures_before_success > 0:
            self.chat_failures_before_success -= 1
            raise LlmAuthenticationError("expired")
        return {
            "model": "GigaChat",
            "choices": [{"message": {"content": "Ответ готов"}}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
        }


class GigaChatAdapterTest(unittest.TestCase):
    def test_chat_uses_structured_messages_without_adapter_owned_history(self) -> None:
        async def scenario() -> None:
            adapter = FakeGigaChatAdapter()
            response = await adapter.chat(
                LlmChatRequest(
                    messages=[
                        LlmMessage(role="system", content="Ты агент требований"),
                        LlmMessage(role="user", content="Проверь CM12345"),
                    ]
                )
            )

            self.assertEqual(response.content, "Ответ готов")
            self.assertEqual(response.usage.total_tokens, 5)
            chat_call = adapter.calls[-1]
            self.assertEqual(len(chat_call["json_payload"]["messages"]), 2)
            self.assertNotIn("conversation_history", chat_call["json_payload"])

        asyncio.run(scenario())

    def test_chat_refreshes_token_once_after_auth_failure(self) -> None:
        async def scenario() -> None:
            adapter = FakeGigaChatAdapter()
            adapter.chat_failures_before_success = 1
            response = await adapter.chat(
                LlmChatRequest(messages=[LlmMessage(role="user", content="ping")])
            )

            self.assertEqual(response.content, "Ответ готов")
            auth_calls = [call for call in adapter.calls if call.get("auth_request")]
            self.assertEqual(len(auth_calls), 2)

        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
