from __future__ import annotations

from typing import Protocol

from agents.coordinator.domain.tasks import CoordinatorCrTask


class TaskRepositoryPort(Protocol):
    async def save(self, task: CoordinatorCrTask) -> None:
        ...

    async def get(self, task_id: str) -> CoordinatorCrTask | None:
        ...

