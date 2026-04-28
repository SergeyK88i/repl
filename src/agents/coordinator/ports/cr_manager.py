from __future__ import annotations

from typing import Protocol

from shared.contracts.tasks import DispatchCrTaskRequest, DispatchCrTaskResult


class CrManagerPort(Protocol):
    async def dispatch_task(self, request: DispatchCrTaskRequest) -> DispatchCrTaskResult:
        ...

