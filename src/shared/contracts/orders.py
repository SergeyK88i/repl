from __future__ import annotations

from pydantic import BaseModel


class CreateOrderRequest(BaseModel):
    source_id: str
    request: str


class OrderResponse(BaseModel):
    order_id: str
    source_id: str
    correlation_id: str
    status: str
    attempts: int
    cr_task_ids: list[str]
    replica_started: bool

