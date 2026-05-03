from __future__ import annotations

from agents.cr_manager.application.service import CrManagerService
from shared.contracts.tasks import DispatchCrTaskRequest, DispatchCrTaskResult


class InProcessCrManagerAdapter:
    def __init__(self, cr_manager: CrManagerService) -> None:
        self.cr_manager = cr_manager

    async def dispatch_task(self, request: DispatchCrTaskRequest) -> DispatchCrTaskResult:
        task = await self.cr_manager.create_task(request)
        return DispatchCrTaskResult(task_id=task.task_id, status=task.status.value)
