from __future__ import annotations

import asyncio
import unittest

from fakes.jira import app as fake_jira


class FakeJiraAppTest(unittest.TestCase):
    def test_create_issue_is_idempotent_by_header(self) -> None:
        async def scenario() -> None:
            fake_jira.store.issues.clear()
            fake_jira.store.issue_by_idempotency_key.clear()
            fake_jira.store.sequence = 0

            request = FakeRequest(
                {
                    "fields": {
                        "project": {"key": "DREAM"},
                        "summary": "Remediation",
                        "description": "Body",
                        "issuetype": {"name": "Task"},
                    }
                },
                idempotency_key="IDEMP-1",
            )

            first = await fake_jira.create_issue(request)
            second = await fake_jira.create_issue(request)

            self.assertEqual(first["key"], "DREAM-1")
            self.assertEqual(second["key"], "DREAM-1")
            self.assertTrue(first["created"])
            self.assertFalse(second["created"])
            self.assertEqual(len(fake_jira.store.issues), 1)

        asyncio.run(scenario())


class FakeRequest:
    def __init__(self, payload: dict, *, idempotency_key: str | None = None) -> None:
        self._payload = payload
        self.headers = {}
        if idempotency_key:
            self.headers["X-Idempotency-Key"] = idempotency_key

    async def json(self) -> dict:
        return self._payload

    def url_for(self, route_name: str, **path_params: str) -> str:
        return f"http://fake-jira/rest/api/3/issue/{path_params['issue_id_or_key']}"


if __name__ == "__main__":
    unittest.main()
