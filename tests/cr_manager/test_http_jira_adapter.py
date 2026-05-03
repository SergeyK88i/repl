from __future__ import annotations

import unittest

from agents.cr_manager.adapters.http.jira import HttpJiraAdapter, HttpJiraAdapterConfig
from agents.cr_manager.ports.jira import CreateJiraIssueRequest


class HttpJiraAdapterTest(unittest.TestCase):
    def test_builds_jira_payload_and_idempotency_header(self) -> None:
        adapter = HttpJiraAdapter(
            HttpJiraAdapterConfig(
                base_url="http://fake-jira",
                browse_url="http://jira.local",
                project_key="DREAM",
            )
        )

        request = CreateJiraIssueRequest(
            idempotency_key="IDEMP-1",
            task_id="TASK-1",
            order_id="ORD-1",
            source_id="SRC-1",
            correlation_id="CORR-1",
            summary="Test summary",
            description="Test description",
            failed_criteria=["C1"],
            failed_items=[],
            remediation_items=[],
            load_plan=None,
            warp_check_id=None,
            attempt=1,
            action="remediate",
        )

        payload = adapter._payload(request)
        headers = adapter._headers(request.idempotency_key)

        fields = payload["fields"]
        self.assertEqual(fields["project"]["key"], "DREAM")
        self.assertEqual(fields["issuetype"]["name"], "Task")
        self.assertEqual(fields["summary"], "Test summary")
        self.assertEqual(fields["description"], "Test description")
        self.assertEqual(headers["X-Idempotency-Key"], "IDEMP-1")


if __name__ == "__main__":
    unittest.main()
