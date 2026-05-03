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
    summary: str
    description: str
    failed_criteria: list[str]
    failed_items: list[dict]
    remediation_items: list[dict]
    load_plan: str | None
    warp_check_id: str | None
    attempt: int
    action: str


@dataclass(frozen=True, slots=True)
class CreateJiraIssueResult:
    issue_id: str
    issue_url: str
    summary: str
    description: str
    created: bool


class JiraPort(Protocol):
    async def create_issue(
        self,
        request: CreateJiraIssueRequest,
    ) -> CreateJiraIssueResult:
        ...
