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
    max_attempts: int = 3


def load_settings() -> Settings:
    profile = os.getenv("ADAPTER_PROFILE", AdapterProfile.MOCK.value)
    max_attempts = int(os.getenv("MAX_ATTEMPTS", "3"))
    return Settings(
        adapter_profile=AdapterProfile(profile),
        max_attempts=max_attempts,
    )

