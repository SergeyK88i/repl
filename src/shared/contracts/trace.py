from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class TraceEvent(BaseModel):
    correlation_id: str
    agent: str
    action: str
    payload: dict = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

