from __future__ import annotations

from agents.coordinator.domain.statuses import OrderStatus


ALLOWED_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.CREATED: {OrderStatus.VALIDATING, OrderStatus.FAILED},
    OrderStatus.VALIDATING: {OrderStatus.WAITING_CR, OrderStatus.READY, OrderStatus.FAILED},
    OrderStatus.WAITING_CR: {OrderStatus.VALIDATING, OrderStatus.FAILED},
    OrderStatus.READY: set(),
    OrderStatus.FAILED: set(),
}


class InvalidOrderTransition(ValueError):
    pass


def ensure_transition_allowed(current: OrderStatus, target: OrderStatus) -> None:
    if target not in ALLOWED_TRANSITIONS[current]:
        raise InvalidOrderTransition(f"Cannot transition order from {current} to {target}")

