from __future__ import annotations

from typing import Protocol

from shared.contracts.readiness import ReadinessCheckRequest, ReadinessCheckResult


class WarpPort(Protocol):
    async def check_readiness(self, request: ReadinessCheckRequest) -> ReadinessCheckResult:
        ...

