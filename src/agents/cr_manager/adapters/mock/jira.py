from __future__ import annotations

from agents.cr_manager.ports.jira import (
    CreateJiraIssueRequest,
    CreateJiraIssueResult,
)


class MockJiraAdapter:
    def __init__(self, *, base_url: str = "https://jira.example/browse") -> None:
        self.base_url = base_url.rstrip("/")
        self._issues_by_key: dict[str, CreateJiraIssueResult] = {}

    async def create_issue(
        self,
        request: CreateJiraIssueRequest,
    ) -> CreateJiraIssueResult:
        existing = self._issues_by_key.get(request.idempotency_key)
        if existing is not None:
            return CreateJiraIssueResult(
                issue_id=existing.issue_id,
                issue_url=existing.issue_url,
                created=False,
            )

        issue_id = f"CR-{request.task_id.removeprefix('TASK-')}"
        result = CreateJiraIssueResult(
            issue_id=issue_id,
            issue_url=f"{self.base_url}/{issue_id}",
            created=True,
        )
        self._issues_by_key[request.idempotency_key] = result
        return result
