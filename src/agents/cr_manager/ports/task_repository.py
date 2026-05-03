from __future__ import annotations

from typing import Protocol

from agents.cr_manager.domain.task import CrManagerTask


class CrManagerTaskRepositoryPort(Protocol):
    async def save(self, task: CrManagerTask) -> None:
        ...

    async def get(self, task_id: str) -> CrManagerTask | None:
        ...

    async def get_by_idempotency_key(self, idempotency_key: str) -> CrManagerTask | None:
        ...

    async def list_by_correlation_id(self, correlation_id: str) -> list[CrManagerTask]:
        ...
