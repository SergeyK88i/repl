from __future__ import annotations

import asyncio
import unittest

from agents.coordinator.adapters.in_memory.order_repository import InMemoryOrderRepository
from agents.coordinator.adapters.in_memory.task_repository import InMemoryTaskRepository
from agents.coordinator.adapters.in_memory.trace import InMemoryTraceAdapter
from agents.coordinator.adapters.in_process.cr_manager import InProcessCrManagerAdapter
from agents.coordinator.adapters.mock.replica_init import MockReplicaInitAdapter
from agents.coordinator.adapters.mock.warp import MockWarpAdapter
from agents.coordinator.application.service import (
    CoordinatorService,
    TaskNotFound,
    TaskOrderMismatch,
)
from agents.coordinator.domain.statuses import OrderStatus
from agents.cr_manager.adapters.in_memory.task_repository import (
    InMemoryCrManagerTaskRepository,
)
from agents.cr_manager.adapters.mock.jira import MockJiraAdapter
from agents.cr_manager.adapters.mock.warp import MockWarpRemediationAdapter
from agents.cr_manager.application.service import CrManagerService
from agents.cr_manager.domain.statuses import CrManagerTaskStatus
from shared.contracts.orders import CreateOrderRequest
from shared.contracts.tasks import TaskCompletedRequest


class CoordinatorServiceTest(unittest.TestCase):
    def test_ready_source_starts_replica_immediately(self) -> None:
        async def scenario() -> None:
            service, _, replica, _ = build_service()
            order = await service.create_order(
                CreateOrderRequest(source_id="SRC-READY", request="load replica")
            )

            self.assertEqual(order.status, OrderStatus.READY)
            self.assertTrue(order.replica_started)
            self.assertEqual(len(replica.started), 1)

        asyncio.run(scenario())

    def test_not_ready_source_dispatches_cr_and_then_ready_after_callback(self) -> None:
        async def scenario() -> None:
            service, cr_manager_tasks, replica, trace = build_service()
            order = await service.create_order(
                CreateOrderRequest(source_id="SRC-123", request="load replica")
            )

            self.assertEqual(order.status, OrderStatus.WAITING_CR)
            self.assertEqual(order.attempts, 1)
            cr_task = await cr_manager_tasks.get(order.cr_task_ids[0])
            self.assertIsNotNone(cr_task)
            self.assertEqual(cr_task.status, CrManagerTaskStatus.JIRA_CREATED)
            self.assertIsNotNone(cr_task.jira_issue_id)
            self.assertIsNotNone(cr_task.jira_issue_url)

            order = await service.handle_task_completed(
                order.order_id,
                TaskCompletedRequest(
                    cr_id=order.cr_task_ids[0],
                    status="done",
                    self_check_passed=True,
                ),
            )

            self.assertEqual(order.status, OrderStatus.READY)
            self.assertTrue(order.replica_started)
            self.assertEqual(len(replica.started), 1)

            events = await trace.list_by_correlation_id(order.correlation_id)
            agents = {event.agent for event in events}
            self.assertIn("coordinator", agents)
            self.assertIn("warp", agents)
            self.assertIn("cr-manager", agents)

        asyncio.run(scenario())

    def test_duplicate_task_completed_callback_is_ignored(self) -> None:
        async def scenario() -> None:
            service, _, replica, _ = build_service()
            order = await service.create_order(
                CreateOrderRequest(source_id="SRC-123", request="load replica")
            )
            task_id = order.cr_task_ids[0]
            request = TaskCompletedRequest(
                cr_id=task_id,
                status="done",
                self_check_passed=True,
            )

            order = await service.handle_task_completed(order.order_id, request)
            order = await service.handle_task_completed(order.order_id, request)

            self.assertEqual(order.status, OrderStatus.READY)
            self.assertTrue(order.replica_started)
            self.assertEqual(len(replica.started), 1)

        asyncio.run(scenario())

    def test_unknown_task_callback_is_rejected(self) -> None:
        async def scenario() -> None:
            service, _, _, _ = build_service()
            order = await service.create_order(
                CreateOrderRequest(source_id="SRC-123", request="load replica")
            )

            with self.assertRaises(TaskNotFound):
                await service.handle_task_completed(
                    order.order_id,
                    TaskCompletedRequest(
                        cr_id="TASK-UNKNOWN",
                        status="done",
                        self_check_passed=True,
                    ),
                )

        asyncio.run(scenario())

    def test_task_callback_for_another_order_is_rejected(self) -> None:
        async def scenario() -> None:
            service, _, _, _ = build_service()
            first = await service.create_order(
                CreateOrderRequest(source_id="SRC-123", request="load replica")
            )
            second = await service.create_order(
                CreateOrderRequest(source_id="SRC-456", request="load replica")
            )

            with self.assertRaises(TaskOrderMismatch):
                await service.handle_task_completed(
                    second.order_id,
                    TaskCompletedRequest(
                        cr_id=first.cr_task_ids[0],
                        status="done",
                        self_check_passed=True,
                    ),
                )

        asyncio.run(scenario())


def build_service() -> tuple[
    CoordinatorService,
    InMemoryCrManagerTaskRepository,
    MockReplicaInitAdapter,
    InMemoryTraceAdapter,
]:
    orders = InMemoryOrderRepository()
    tasks = InMemoryTaskRepository()
    trace = InMemoryTraceAdapter()
    warp = MockWarpAdapter(trace=trace)
    cr_manager_tasks = InMemoryCrManagerTaskRepository()
    cr_manager_service = CrManagerService(
        tasks=cr_manager_tasks,
        jira=MockJiraAdapter(),
        warp=MockWarpRemediationAdapter(),
        trace=trace,
    )
    cr_manager = InProcessCrManagerAdapter(cr_manager_service)
    replica = MockReplicaInitAdapter()
    service = CoordinatorService(
        orders=orders,
        tasks=tasks,
        trace=trace,
        warp=warp,
        cr_manager=cr_manager,
        replica_init=replica,
    )
    return service, cr_manager_tasks, replica, trace


if __name__ == "__main__":
    unittest.main()
