from __future__ import annotations

from pydantic import BaseModel, Field

from agents.coordinator.domain.statuses import OrderStatus


class Order(BaseModel):
    order_id: str
    source_id: str
    request: str
    correlation_id: str
    status: OrderStatus = OrderStatus.CREATED
    attempts: int = 0
    cr_task_ids: list[str] = Field(default_factory=list)
    replica_started: bool = False

