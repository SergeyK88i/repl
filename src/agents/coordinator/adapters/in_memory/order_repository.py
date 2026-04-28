from __future__ import annotations

from agents.coordinator.domain.order import Order


class InMemoryOrderRepository:
    def __init__(self) -> None:
        self._orders: dict[str, Order] = {}

    async def save(self, order: Order) -> None:
        self._orders[order.order_id] = order.model_copy(deep=True)

    async def get(self, order_id: str) -> Order | None:
        order = self._orders.get(order_id)
        return order.model_copy(deep=True) if order else None

