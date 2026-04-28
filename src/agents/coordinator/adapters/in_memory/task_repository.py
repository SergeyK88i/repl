from __future__ import annotations

from agents.coordinator.domain.tasks import CoordinatorCrTask


class InMemoryTaskRepository:
    def __init__(self) -> None:
        self._tasks: dict[str, CoordinatorCrTask] = {}

    async def save(self, task: CoordinatorCrTask) -> None:
        self._tasks[task.task_id] = task.model_copy(deep=True)

    async def get(self, task_id: str) -> CoordinatorCrTask | None:
        task = self._tasks.get(task_id)
        return task.model_copy(deep=True) if task else None

