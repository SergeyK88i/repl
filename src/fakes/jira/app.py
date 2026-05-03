from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

app = FastAPI(title="Fake Jira API")


class FakeJiraStore:
    def __init__(self) -> None:
        self.issues: dict[str, dict[str, Any]] = {}
        self.issue_by_idempotency_key: dict[str, str] = {}
        self.sequence = 0

    def next_key(self, project_key: str) -> str:
        self.sequence += 1
        return f"{project_key}-{self.sequence}"


store = FakeJiraStore()


class CommentRequest(BaseModel):
    body: Any


class TransitionRequest(BaseModel):
    transition: dict[str, Any] = Field(default_factory=dict)


@app.post("/rest/api/3/issue", status_code=201)
async def create_issue(request: Request) -> dict[str, Any]:
    payload = await request.json()
    idempotency_key = request.headers.get("X-Idempotency-Key")
    if idempotency_key and idempotency_key in store.issue_by_idempotency_key:
        key = store.issue_by_idempotency_key[idempotency_key]
        issue = store.issues[key]
        return {
            "id": issue["id"],
            "key": issue["key"],
            "self": issue["self"],
            "created": False,
        }

    fields = payload.get("fields") or {}
    project_key = str((fields.get("project") or {}).get("key") or "DREAM")
    key = store.next_key(project_key)
    now = datetime.now(timezone.utc).isoformat()
    issue = {
        "id": str(store.sequence),
        "key": key,
        "self": str(request.url_for("get_issue", issue_id_or_key=key)),
        "fields": fields,
        "properties": payload.get("properties", []),
        "comments": [],
        "status": {"id": "1", "name": "To Do"},
        "created": now,
        "updated": now,
    }
    store.issues[key] = issue
    if idempotency_key:
        store.issue_by_idempotency_key[idempotency_key] = key
    return {
        "id": issue["id"],
        "key": issue["key"],
        "self": issue["self"],
        "created": True,
    }


@app.get("/rest/api/3/issue/{issue_id_or_key}", name="get_issue")
async def get_issue(issue_id_or_key: str) -> dict[str, Any]:
    issue = _find_issue(issue_id_or_key)
    return issue


@app.post("/rest/api/3/issue/{issue_id_or_key}/comment", status_code=201)
async def add_comment(issue_id_or_key: str, request: CommentRequest) -> dict[str, Any]:
    issue = _find_issue(issue_id_or_key)
    comment = {
        "id": str(len(issue["comments"]) + 1),
        "body": request.body,
        "created": datetime.now(timezone.utc).isoformat(),
    }
    issue["comments"].append(comment)
    issue["updated"] = comment["created"]
    return comment


@app.get("/rest/api/3/issue/{issue_id_or_key}/transitions")
async def get_transitions(issue_id_or_key: str) -> dict[str, Any]:
    _find_issue(issue_id_or_key)
    return {
        "transitions": [
            {"id": "11", "name": "In Progress"},
            {"id": "31", "name": "Done"},
        ]
    }


@app.post("/rest/api/3/issue/{issue_id_or_key}/transitions", status_code=204)
async def transition_issue(
    issue_id_or_key: str,
    request: TransitionRequest,
) -> None:
    issue = _find_issue(issue_id_or_key)
    transition = request.transition
    issue["status"] = {
        "id": str(transition.get("id") or ""),
        "name": str(transition.get("name") or transition.get("id") or "Unknown"),
    }
    issue["updated"] = datetime.now(timezone.utc).isoformat()


def _find_issue(issue_id_or_key: str) -> dict[str, Any]:
    issue = store.issues.get(issue_id_or_key)
    if issue is not None:
        return issue
    for candidate in store.issues.values():
        if candidate["id"] == issue_id_or_key:
            return candidate
    raise HTTPException(status_code=404, detail="Issue not found")
