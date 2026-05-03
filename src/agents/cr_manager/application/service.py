from __future__ import annotations

from agents.cr_manager.domain.task import CrManagerTask
from agents.cr_manager.ports.task_repository import CrManagerTaskRepositoryPort
from agents.cr_manager.ports.trace import TracePort
from shared.contracts.tasks import DispatchCrTaskRequest
from shared.contracts.trace import TraceEvent
from shared.domain.ids import new_agent_run_id, new_task_id


class CrManagerTaskNotFound(LookupError):
    pass


class CrManagerService:
    def __init__(
        self,
        *,
        tasks: CrManagerTaskRepositoryPort,
        trace: TracePort,
    ) -> None:
        self.tasks = tasks
        self.trace = trace

    async def create_task(self, request: DispatchCrTaskRequest) -> CrManagerTask:
        task = CrManagerTask(
            task_id=new_task_id(),
            order_id=request.order_id,
            source_id=request.source_id,
            correlation_id=request.correlation_id,
            agent_run_id=new_agent_run_id(),
            failed_criteria=list(request.failed_criteria),
            attempt=request.attempt,
            action=request.action,
        )
        await self.tasks.save(task)
        await self._trace(
            task,
            "cr_task_received",
            {
                "order_id": task.order_id,
                "source_id": task.source_id,
                "attempt": task.attempt,
                "action": task.action,
                "failed_criteria": task.failed_criteria,
            },
        )
        return task

    async def get_task(self, task_id: str) -> CrManagerTask:
        task = await self.tasks.get(task_id)
        if task is None:
            raise CrManagerTaskNotFound(task_id)
        return task

    async def list_tasks(self, correlation_id: str) -> list[CrManagerTask]:
        return await self.tasks.list_by_correlation_id(correlation_id)

    async def _trace(self, task: CrManagerTask, action: str, payload: dict) -> None:
        await self.trace.write(
            TraceEvent(
                correlation_id=task.correlation_id,
                agent="cr-manager",
                action=action,
                payload={
                    "task_id": task.task_id,
                    "agent_run_id": task.agent_run_id,
                    **payload,
                },
            )
        )
