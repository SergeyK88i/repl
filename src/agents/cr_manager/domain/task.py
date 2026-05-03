from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from agents.cr_manager.domain.statuses import CrManagerTaskStatus


@dataclass(slots=True)
class CrManagerTask:
    task_id: str
    order_id: str
    source_id: str
    correlation_id: str
    agent_run_id: str
    failed_criteria: list[str]
    failed_items: list[dict]
    load_plan: str | None
    warp_check_id: str | None
    attempt: int
    action: str
    idempotency_key: str
    status: CrManagerTaskStatus = CrManagerTaskStatus.RECEIVED
    jira_issue_id: str | None = None
    jira_issue_url: str | None = None
    jira_summary: str | None = None
    jira_description: str | None = None
    remediation_items: list[dict] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc)
