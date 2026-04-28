from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class CoordinatorTaskStatus(str, Enum):
    DISPATCHED = "DISPATCHED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class CoordinatorCrTask(BaseModel):
    task_id: str
    order_id: str
    source_id: str
    correlation_id: str
    agent_run_id: str
    attempt: int
    failed_criteria: list[str] = Field(default_factory=list)
    status: CoordinatorTaskStatus = CoordinatorTaskStatus.DISPATCHED
    completion_status: str | None = None
    self_check_passed: bool | None = None

