from __future__ import annotations

from pydantic import BaseModel, Field


class FailedCriterionItem(BaseModel):
    criteria_id: str
    failed_params: list[str] = Field(default_factory=list)


class DispatchCrTaskRequest(BaseModel):
    order_id: str
    source_id: str
    correlation_id: str
    failed_criteria: list[str]
    failed_items: list[FailedCriterionItem] = Field(default_factory=list)
    load_plan: str | None = None
    warp_check_id: str | None = None
    attempt: int
    action: str = "remediate"
    idempotency_key: str | None = None


class DispatchCrTaskResult(BaseModel):
    task_id: str
    status: str


class TaskCompletedRequest(BaseModel):
    cr_id: str
    status: str
    self_check_passed: bool
    failed_criteria: list[str] = Field(default_factory=list)
