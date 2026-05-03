from __future__ import annotations

import base64
from dataclasses import dataclass

import aiohttp

from agents.cr_manager.ports.jira import (
    CreateJiraIssueRequest,
    CreateJiraIssueResult,
)


@dataclass(frozen=True, slots=True)
class HttpJiraAdapterConfig:
    base_url: str
    project_key: str
    issue_type: str = "Task"
    browse_url: str | None = None
    email: str | None = None
    api_token: str | None = None
    bearer_token: str | None = None
    timeout_seconds: float = 30.0


class HttpJiraAdapter:
    def __init__(self, config: HttpJiraAdapterConfig) -> None:
        self.config = config
        self.base_url = config.base_url.rstrip("/")
        self.browse_url = (config.browse_url or config.base_url).rstrip("/")

    async def create_issue(
        self,
        request: CreateJiraIssueRequest,
    ) -> CreateJiraIssueResult:
        payload = self._payload(request)
        headers = self._headers(request.idempotency_key)
        timeout = aiohttp.ClientTimeout(total=self.config.timeout_seconds)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                f"{self.base_url}/rest/api/3/issue",
                headers=headers,
                json=payload,
            ) as response:
                data = await response.json(content_type=None)
                if response.status not in {200, 201}:
                    raise RuntimeError(f"Jira create issue failed: {response.status} {data}")

        issue_id = str(data.get("key") or data.get("id"))
        created = bool(data.get("created", response.status == 201))
        return CreateJiraIssueResult(
            issue_id=issue_id,
            issue_url=f"{self.browse_url}/browse/{issue_id}",
            summary=request.summary,
            description=request.description,
            created=created,
        )

    def _payload(self, request: CreateJiraIssueRequest) -> dict:
        return {
            "fields": {
                "project": {"key": self.config.project_key},
                "summary": request.summary,
                "description": request.description,
                "issuetype": {"name": self.config.issue_type},
                "labels": ["dream-remediation", "agent-created"],
            },
            "properties": [
                {
                    "key": "dream.idempotency_key",
                    "value": request.idempotency_key,
                },
                {
                    "key": "dream.cr_manager_context",
                    "value": {
                        "task_id": request.task_id,
                        "order_id": request.order_id,
                        "source_id": request.source_id,
                        "correlation_id": request.correlation_id,
                        "attempt": request.attempt,
                        "action": request.action,
                        "load_plan": request.load_plan,
                        "warp_check_id": request.warp_check_id,
                    },
                },
            ],
        }

    def _headers(self, idempotency_key: str) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Idempotency-Key": idempotency_key,
        }
        if self.config.bearer_token:
            headers["Authorization"] = f"Bearer {self.config.bearer_token}"
        elif self.config.email and self.config.api_token:
            raw = f"{self.config.email}:{self.config.api_token}".encode("utf-8")
            headers["Authorization"] = f"Basic {base64.b64encode(raw).decode('ascii')}"
        return headers
