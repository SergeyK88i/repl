from __future__ import annotations

from agents.coordinator.domain.order import Order
from agents.coordinator.domain.state_machine import ensure_transition_allowed
from agents.coordinator.domain.statuses import OrderStatus
from agents.coordinator.domain.tasks import CoordinatorCrTask, CoordinatorTaskStatus
from agents.coordinator.ports.cr_manager import CrManagerPort
from agents.coordinator.ports.order_repository import OrderRepositoryPort
from agents.coordinator.ports.replica_init import ReplicaInitPort
from agents.coordinator.ports.task_repository import TaskRepositoryPort
from agents.coordinator.ports.trace import TracePort
from agents.coordinator.ports.warp import WarpPort
from shared.contracts.orders import CreateOrderRequest
from shared.contracts.readiness import (
    ReadinessCheckRequest,
    ReadinessContext,
    ReadinessStatus,
)
from shared.contracts.replica import ReplicaInitRequest
from shared.contracts.tasks import DispatchCrTaskRequest, TaskCompletedRequest
from shared.contracts.trace import TraceEvent
from shared.domain.ids import new_agent_run_id, new_correlation_id, new_order_id


class OrderNotFound(LookupError):
    pass


class TaskNotFound(LookupError):
    pass


class TaskOrderMismatch(ValueError):
    pass


class TaskCallbackNotAllowed(ValueError):
    pass


class CoordinatorService:
    def __init__(
        self,
        *,
        orders: OrderRepositoryPort,
        tasks: TaskRepositoryPort,
        warp: WarpPort,
        cr_manager: CrManagerPort,
        replica_init: ReplicaInitPort,
        trace: TracePort,
        max_attempts: int = 3,
    ) -> None:
        self.orders = orders
        self.tasks = tasks
        self.warp = warp
        self.cr_manager = cr_manager
        self.replica_init = replica_init
        self.trace = trace
        self.max_attempts = max_attempts

    async def create_order(self, request: CreateOrderRequest) -> Order:
        order = Order(
            order_id=new_order_id(),
            source_id=request.source_id,
            request=request.request,
            correlation_id=new_correlation_id(),
        )
        await self.orders.save(order)
        await self._trace(order, "order_created", {"source_id": order.source_id})
        return await self._validate_order(order, ReadinessContext.INITIAL_CHECK)

    async def get_order(self, order_id: str) -> Order:
        order = await self.orders.get(order_id)
        if order is None:
            raise OrderNotFound(order_id)
        return order

    async def handle_task_completed(
        self,
        order_id: str,
        request: TaskCompletedRequest,
    ) -> Order:
        order = await self.get_order(order_id)
        task = await self.tasks.get(request.cr_id)
        if task is None:
            raise TaskNotFound(request.cr_id)
        if task.order_id != order.order_id:
            raise TaskOrderMismatch(
                f"Task {task.task_id} does not belong to order {order.order_id}"
            )

        if task.status in {CoordinatorTaskStatus.COMPLETED, CoordinatorTaskStatus.FAILED}:
            await self._trace(
                order,
                "cr_task_completion_duplicate_ignored",
                {"cr_id": request.cr_id, "task_status": task.status.value},
            )
            return order

        if order.status != OrderStatus.WAITING_CR:
            raise TaskCallbackNotAllowed(
                f"Order {order.order_id} is {order.status}; expected WAITING_CR"
            )

        await self._trace(
            order,
            "cr_task_completed_received",
            {
                "cr_id": request.cr_id,
                "status": request.status,
                "self_check_passed": request.self_check_passed,
                "failed_criteria": request.failed_criteria,
            },
        )

        task.status = (
            CoordinatorTaskStatus.COMPLETED
            if request.self_check_passed
            else CoordinatorTaskStatus.FAILED
        )
        task.completion_status = request.status
        task.self_check_passed = request.self_check_passed
        await self.tasks.save(task)

        if not request.self_check_passed:
            return await self._retry_or_fail(
                order,
                request.failed_criteria,
                reason="cr_self_check_failed",
            )

        return await self._validate_order(order, ReadinessContext.FINAL_CHECK)

    async def list_trace(self, correlation_id: str) -> list[TraceEvent]:
        return await self.trace.list_by_correlation_id(correlation_id)

    async def _validate_order(self, order: Order, context: ReadinessContext) -> Order:
        await self._change_status(order, OrderStatus.VALIDATING)
        result = await self.warp.check_readiness(
            ReadinessCheckRequest(
                source_id=order.source_id,
                context=context,
                correlation_id=order.correlation_id,
            )
        )
        await self._trace(
            order,
            "warp_readiness_checked",
            {
                "context": context.value,
                "status": result.status.value,
                "score": result.score.model_dump() if result.score else None,
                "failed_criteria": result.failed_criteria,
                "audit_hash": result.audit_hash,
                "regression": result.regression,
            },
        )

        if result.status == ReadinessStatus.READY:
            await self._change_status(order, OrderStatus.READY)
            await self._start_replica(order)
            return order

        return await self._retry_or_fail(
            order,
            result.failed_criteria,
            reason="warp_not_ready",
        )

    async def _retry_or_fail(
        self,
        order: Order,
        failed_criteria: list[str],
        *,
        reason: str,
    ) -> Order:
        if order.attempts >= self.max_attempts:
            await self._change_status(order, OrderStatus.FAILED)
            await self._trace(
                order,
                "order_escalated",
                {"reason": reason, "failed_criteria": failed_criteria},
            )
            return order

        order.attempts += 1
        await self._change_status(order, OrderStatus.WAITING_CR)
        task = await self.cr_manager.dispatch_task(
            DispatchCrTaskRequest(
                order_id=order.order_id,
                source_id=order.source_id,
                correlation_id=order.correlation_id,
                failed_criteria=failed_criteria,
                attempt=order.attempts,
                action="retry" if order.attempts > 1 else "remediate",
            )
        )
        await self.tasks.save(
            CoordinatorCrTask(
                task_id=task.task_id,
                order_id=order.order_id,
                source_id=order.source_id,
                correlation_id=order.correlation_id,
                agent_run_id=new_agent_run_id(),
                attempt=order.attempts,
                failed_criteria=failed_criteria,
            )
        )
        order.cr_task_ids.append(task.task_id)
        await self.orders.save(order)
        await self._trace(
            order,
            "cr_task_dispatched",
            {
                "task_id": task.task_id,
                "task_status": task.status,
                "attempt": order.attempts,
                "failed_criteria": failed_criteria,
            },
        )
        return order

    async def _start_replica(self, order: Order) -> None:
        if order.replica_started:
            return
        result = await self.replica_init.start(
            ReplicaInitRequest(
                order_id=order.order_id,
                source_id=order.source_id,
                correlation_id=order.correlation_id,
            )
        )
        order.replica_started = result.accepted
        await self.orders.save(order)
        await self._trace(
            order,
            "replica_init_requested",
            {"accepted": result.accepted, "replica_job_id": result.replica_job_id},
        )

    async def _change_status(self, order: Order, status: OrderStatus) -> None:
        if order.status == status:
            return
        ensure_transition_allowed(order.status, status)
        previous = order.status
        order.status = status
        await self.orders.save(order)
        await self._trace(
            order,
            "status_changed",
            {"from": previous.value, "to": status.value},
        )

    async def _trace(self, order: Order, action: str, payload: dict) -> None:
        await self.trace.write(
            TraceEvent(
                correlation_id=order.correlation_id,
                agent="coordinator",
                action=action,
                payload={"order_id": order.order_id, **payload},
            )
        )
