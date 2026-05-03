from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

from shared.adapters.llm.gigachat import GigaChatAdapter, GigaChatAdapterConfig
from shared.contracts.llm import LlmChatRequest, LlmEmbeddingRequest, LlmMessage


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a real LLM smoke test.")
    parser.add_argument(
        "--message",
        default="Ответь одним предложением: LLM adapter подключён корректно?",
        help="User message to send to the model.",
    )
    parser.add_argument(
        "--system",
        default="Ты технический smoke-test ассистент. Отвечай кратко.",
        help="System message to send to the model.",
    )
    parser.add_argument(
        "--embedding",
        action="store_true",
        help="Also request an embedding for the user message.",
    )
    return parser


async def main() -> int:
    args = build_parser().parse_args()
    auth_token = os.getenv("GIGACHAT_AUTH_TOKEN")
    if not auth_token:
        print("GIGACHAT_AUTH_TOKEN is not set", file=sys.stderr)
        return 2

    adapter = GigaChatAdapter(
        GigaChatAdapterConfig(
            auth_token=auth_token,
            scope=os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS"),
            model=os.getenv("GIGACHAT_MODEL", "GigaChat"),
            embeddings_model=os.getenv("GIGACHAT_EMBEDDINGS_MODEL", "Embeddings"),
            oauth_url=os.getenv(
                "GIGACHAT_OAUTH_URL",
                "https://ngw.devices.sberbank.ru:9443/api/v2/oauth",
            ),
            chat_url=os.getenv(
                "GIGACHAT_CHAT_URL",
                "https://gigachat.devices.sberbank.ru/api/v1/chat/completions",
            ),
            embeddings_url=os.getenv(
                "GIGACHAT_EMBEDDINGS_URL",
                "https://gigachat.devices.sberbank.ru/api/v1/embeddings",
            ),
            timeout_seconds=float(os.getenv("GIGACHAT_TIMEOUT_SECONDS", "60")),
            verify_ssl=_env_bool("GIGACHAT_VERIFY_SSL", default=True),
            ca_bundle_path=os.getenv("GIGACHAT_CA_BUNDLE_PATH"),
        )
    )

    chat_response = await adapter.chat(
        LlmChatRequest(
            messages=[
                LlmMessage(role="system", content=args.system),
                LlmMessage(role="user", content=args.message),
            ],
        )
    )
    output: dict[str, object] = {
        "chat": {
            "model": chat_response.model,
            "content": chat_response.content,
            "function_call": (
                chat_response.function_call.model_dump()
                if chat_response.function_call
                else None
            ),
            "usage": chat_response.usage.model_dump() if chat_response.usage else None,
        }
    }

    if args.embedding:
        embedding_response = await adapter.embed(LlmEmbeddingRequest(text=args.message))
        output["embedding"] = {
            "model": embedding_response.model,
            "dimensions": len(embedding_response.embedding),
            "preview": embedding_response.embedding[:5],
        }

    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


def _env_bool(name: str, *, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
