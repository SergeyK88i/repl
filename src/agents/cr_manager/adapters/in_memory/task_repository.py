from __future__ import annotations

from agents.cr_manager.domain.task import CrManagerTask


class InMemoryCrManagerTaskRepository:
    def __init__(self) -> None:
        self._tasks: dict[str, CrManagerTask] = {}

    async def save(self, task: CrManagerTask) -> None:
        self._tasks[task.task_id] = task

    async def get(self, task_id: str) -> CrManagerTask | None:
        return self._tasks.get(task_id)

    async def get_by_idempotency_key(self, idempotency_key: str) -> CrManagerTask | None:
        for task in self._tasks.values():
            if task.idempotency_key == idempotency_key:
                return task
        return None

    async def list_by_correlation_id(self, correlation_id: str) -> list[CrManagerTask]:
        return [
            task
            for task in self._tasks.values()
            if task.correlation_id == correlation_id
        ]
