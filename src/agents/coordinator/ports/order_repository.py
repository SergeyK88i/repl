from __future__ import annotations

from typing import Protocol

from agents.coordinator.domain.order import Order


class OrderRepositoryPort(Protocol):
    async def save(self, order: Order) -> None:
        ...

    async def get(self, order_id: str) -> Order | None:
        ...

