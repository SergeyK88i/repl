from __future__ import annotations

import asyncio
import unittest

from fastapi import HTTPException

from agents.coordinator.adapters.in_memory.trace import InMemoryTraceAdapter
from agents.cr_manager.adapters.in_memory.task_repository import (
    InMemoryCrManagerTaskRepository,
)
from agents.cr_manager.adapters.mock.jira import MockJiraAdapter
from agents.cr_manager.api.routes import create_task, get_task
from agents.cr_manager.application.service import CrManagerService
from shared.contracts.tasks import DispatchCrTaskRequest


class CrManagerRoutesTest(unittest.TestCase):
    def test_create_and_get_task(self) -> None:
        async def scenario() -> None:
            service = build_service()

            created = await create_task(
                DispatchCrTaskRequest(
                    order_id="ORD-ROUTE",
                    source_id="SRC-ROUTE",
                    correlation_id="CORR-ROUTE",
                    failed_criteria=["C1", "C3.P2"],
                    attempt=1,
                    action="remediate",
                ),
                cr_manager=service,
            )

            self.assertTrue(created.task_id.startswith("TASK-"))
            self.assertEqual(created.status, "JIRA_CREATED")
            self.assertEqual(created.order_id, "ORD-ROUTE")
            self.assertEqual(created.failed_criteria, ["C1", "C3.P2"])
            self.assertIsNotNone(created.jira_issue_id)
            self.assertIsNotNone(created.jira_issue_url)

            fetched = await get_task(created.task_id, cr_manager=service)
            self.assertEqual(fetched.task_id, created.task_id)

        asyncio.run(scenario())

    def test_get_unknown_task_returns_404(self) -> None:
        async def scenario() -> None:
            service = build_service()

            with self.assertRaises(HTTPException) as context:
                await get_task("TASK-UNKNOWN", cr_manager=service)

            self.assertEqual(context.exception.status_code, 404)

        asyncio.run(scenario())


def build_service() -> CrManagerService:
    return CrManagerService(
        tasks=InMemoryCrManagerTaskRepository(),
        jira=MockJiraAdapter(),
        trace=InMemoryTraceAdapter(),
    )


if __name__ == "__main__":
    unittest.main()
