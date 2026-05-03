from __future__ import annotations

import asyncio
import unittest

from agents.coordinator.adapters.in_memory.trace import InMemoryTraceAdapter
from agents.cr_manager.adapters.in_memory.task_repository import (
    InMemoryCrManagerTaskRepository,
)
from agents.cr_manager.application.service import (
    CrManagerService,
    CrManagerTaskNotFound,
)
from agents.cr_manager.domain.statuses import CrManagerTaskStatus
from shared.contracts.tasks import DispatchCrTaskRequest


class CrManagerServiceTest(unittest.TestCase):
    def test_create_task_persists_task_and_writes_trace(self) -> None:
        async def scenario() -> None:
            service, trace = build_service()

            task = await service.create_task(
                DispatchCrTaskRequest(
                    order_id="ORD-123",
                    source_id="SRC-123",
                    correlation_id="CORR-123",
                    failed_criteria=["C1", "C3.P2"],
                    attempt=1,
                )
            )

            self.assertTrue(task.task_id.startswith("TASK-"))
            self.assertEqual(task.status, CrManagerTaskStatus.RECEIVED)
            self.assertEqual(task.order_id, "ORD-123")
            self.assertEqual(task.source_id, "SRC-123")
            self.assertEqual(task.failed_criteria, ["C1", "C3.P2"])
            self.assertEqual(task.attempt, 1)
            self.assertEqual(task.action, "remediate")

            stored = await service.get_task(task.task_id)
            self.assertEqual(stored.task_id, task.task_id)

            events = await trace.list_by_correlation_id("CORR-123")
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0].agent, "cr-manager")
            self.assertEqual(events[0].action, "cr_task_received")
            self.assertEqual(events[0].payload["task_id"], task.task_id)
            self.assertEqual(events[0].payload["failed_criteria"], ["C1", "C3.P2"])

        asyncio.run(scenario())

    def test_get_unknown_task_raises_not_found(self) -> None:
        async def scenario() -> None:
            service, _ = build_service()

            with self.assertRaises(CrManagerTaskNotFound):
                await service.get_task("TASK-UNKNOWN")

        asyncio.run(scenario())

    def test_list_tasks_by_correlation_id(self) -> None:
        async def scenario() -> None:
            service, _ = build_service()

            first = await service.create_task(
                DispatchCrTaskRequest(
                    order_id="ORD-1",
                    source_id="SRC-1",
                    correlation_id="CORR-SAME",
                    failed_criteria=["C1"],
                    attempt=1,
                )
            )
            await service.create_task(
                DispatchCrTaskRequest(
                    order_id="ORD-2",
                    source_id="SRC-2",
                    correlation_id="CORR-OTHER",
                    failed_criteria=["C2"],
                    attempt=1,
                )
            )

            tasks = await service.list_tasks("CORR-SAME")
            self.assertEqual([task.task_id for task in tasks], [first.task_id])

        asyncio.run(scenario())


def build_service() -> tuple[CrManagerService, InMemoryTraceAdapter]:
    trace = InMemoryTraceAdapter()
    service = CrManagerService(
        tasks=InMemoryCrManagerTaskRepository(),
        trace=trace,
    )
    return service, trace


if __name__ == "__main__":
    unittest.main()
