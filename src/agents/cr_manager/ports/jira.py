from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class CreateJiraIssueRequest:
    idempotency_key: str
    task_id: str
    order_id: str
    source_id: str
    correlation_id: str
    failed_criteria: list[str]
    attempt: int
    action: str


@dataclass(frozen=True, slots=True)
class CreateJiraIssueResult:
    issue_id: str
    issue_url: str
    created: bool


class JiraPort(Protocol):
    async def create_issue(
        self,
        request: CreateJiraIssueRequest,
    ) -> CreateJiraIssueResult:
        ...
