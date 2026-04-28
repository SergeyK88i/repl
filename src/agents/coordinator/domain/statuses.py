from __future__ import annotations

from enum import Enum


class OrderStatus(str, Enum):
    CREATED = "CREATED"
    VALIDATING = "VALIDATING"
    WAITING_CR = "WAITING_CR"
    READY = "READY"
    FAILED = "FAILED"

