from __future__ import annotations

from pydantic import BaseModel


class ReplicaInitRequest(BaseModel):
    order_id: str
    source_id: str
    correlation_id: str


class ReplicaInitResult(BaseModel):
    accepted: bool
    replica_job_id: str | None = None

