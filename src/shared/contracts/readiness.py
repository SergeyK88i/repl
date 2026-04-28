from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ReadinessStatus(str, Enum):
    READY = "READY"
    NOT_READY = "NOT_READY"


class ReadinessContext(str, Enum):
    INITIAL_CHECK = "initial_check"
    SELF_CHECK = "self_check"
    FINAL_CHECK = "final_check"


class ReadinessScore(BaseModel):
    current: int
    required: int


class ReadinessCheckRequest(BaseModel):
    source_id: str
    context: ReadinessContext
    correlation_id: str


class ReadinessCheckResult(BaseModel):
    status: ReadinessStatus
    score: ReadinessScore | None = None
    failed_criteria: list[str] = Field(default_factory=list)
    audit_hash: str | None = None
    regression: bool = False

