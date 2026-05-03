from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum


class AdapterProfile(str, Enum):
    MOCK = "mock"
    HTTP = "http"


@dataclass(frozen=True)
class Settings:
    adapter_profile: AdapterProfile = AdapterProfile.MOCK
    jira_adapter_profile: AdapterProfile = AdapterProfile.MOCK
    max_attempts: int = 3
    jira_base_url: str = "http://127.0.0.1:9001"
    jira_browse_url: str | None = None
    jira_project_key: str = "DREAM"
    jira_issue_type: str = "Task"
    jira_email: str | None = None
    jira_api_token: str | None = None
    jira_bearer_token: str | None = None
    jira_timeout_seconds: float = 30.0
    gigachat_auth_token: str | None = None
    gigachat_scope: str = "GIGACHAT_API_PERS"
    gigachat_model: str = "GigaChat"
    gigachat_embeddings_model: str = "Embeddings"
    gigachat_oauth_url: str = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
    gigachat_chat_url: str = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
    gigachat_embeddings_url: str = "https://gigachat.devices.sberbank.ru/api/v1/embeddings"
    gigachat_timeout_seconds: float = 60.0
    gigachat_verify_ssl: bool = True
    gigachat_ca_bundle_path: str | None = None


def load_settings() -> Settings:
    profile = os.getenv("ADAPTER_PROFILE", AdapterProfile.MOCK.value)
    jira_profile = os.getenv("JIRA_ADAPTER_PROFILE", profile)
    max_attempts = int(os.getenv("MAX_ATTEMPTS", "3"))
    return Settings(
        adapter_profile=AdapterProfile(profile),
        jira_adapter_profile=AdapterProfile(jira_profile),
        max_attempts=max_attempts,
        jira_base_url=os.getenv("JIRA_BASE_URL", "http://127.0.0.1:9001"),
        jira_browse_url=os.getenv("JIRA_BROWSE_URL"),
        jira_project_key=os.getenv("JIRA_PROJECT_KEY", "DREAM"),
        jira_issue_type=os.getenv("JIRA_ISSUE_TYPE", "Task"),
        jira_email=os.getenv("JIRA_EMAIL"),
        jira_api_token=os.getenv("JIRA_API_TOKEN"),
        jira_bearer_token=os.getenv("JIRA_BEARER_TOKEN"),
        jira_timeout_seconds=float(os.getenv("JIRA_TIMEOUT_SECONDS", "30")),
        gigachat_auth_token=os.getenv("GIGACHAT_AUTH_TOKEN"),
        gigachat_scope=os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS"),
        gigachat_model=os.getenv("GIGACHAT_MODEL", "GigaChat"),
        gigachat_embeddings_model=os.getenv("GIGACHAT_EMBEDDINGS_MODEL", "Embeddings"),
        gigachat_oauth_url=os.getenv(
            "GIGACHAT_OAUTH_URL",
            "https://ngw.devices.sberbank.ru:9443/api/v2/oauth",
        ),
        gigachat_chat_url=os.getenv(
            "GIGACHAT_CHAT_URL",
            "https://gigachat.devices.sberbank.ru/api/v1/chat/completions",
        ),
        gigachat_embeddings_url=os.getenv(
            "GIGACHAT_EMBEDDINGS_URL",
            "https://gigachat.devices.sberbank.ru/api/v1/embeddings",
        ),
        gigachat_timeout_seconds=float(os.getenv("GIGACHAT_TIMEOUT_SECONDS", "60")),
        gigachat_verify_ssl=_env_bool("GIGACHAT_VERIFY_SSL", default=True),
        gigachat_ca_bundle_path=os.getenv("GIGACHAT_CA_BUNDLE_PATH"),
    )


def _env_bool(name: str, *, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}
