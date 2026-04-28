from __future__ import annotations

from shared.contracts.tasks import DispatchCrTaskRequest, DispatchCrTaskResult
from shared.contracts.trace import TraceEvent
from shared.domain.ids import new_task_id


class MockCrManagerAdapter:
    def __init__(self, trace=None) -> None:
        self.trace = trace
        self.dispatched_tasks: list[DispatchCrTaskRequest] = []

    async def dispatch_task(self, request: DispatchCrTaskRequest) -> DispatchCrTaskResult:
        await self._trace(
            request,
            "task_dispatch_received",
            {
                "order_id": request.order_id,
                "source_id": request.source_id,
                "failed_criteria": request.failed_criteria,
                "attempt": request.attempt,
                "action": request.action,
            },
        )
        self.dispatched_tasks.append(request)
        result = DispatchCrTaskResult(task_id=new_task_id(), status="accepted")
        await self._trace(
            request,
            "task_accepted",
            {"order_id": request.order_id, "task_id": result.task_id},
        )
        return result

    async def _trace(
        self,
        request: DispatchCrTaskRequest,
        action: str,
        payload: dict,
    ) -> None:
        if self.trace is None:
            return
        await self.trace.write(
            TraceEvent(
                correlation_id=request.correlation_id,
                agent="cr-manager",
                action=action,
                payload=payload,
            )
        )
