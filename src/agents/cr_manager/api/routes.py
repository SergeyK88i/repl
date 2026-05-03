from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from agents.cr_manager.application.service import (
    CrManagerService,
    CrManagerTaskNotFound,
)
from agents.cr_manager.domain.task import CrManagerTask
from app.config.container import AppContainer, get_container
from shared.contracts.tasks import DispatchCrTaskRequest

router = APIRouter(prefix="/cr-manager", tags=["cr-manager"])


class CrManagerTaskResponse(BaseModel):
    task_id: str
    order_id: str
    source_id: str
    correlation_id: str
    agent_run_id: str
    status: str
    failed_criteria: list[str]
    attempt: int
    action: str
    jira_issue_id: str | None
    jira_issue_url: str | None
    created_at: datetime
    updated_at: datetime


def get_cr_manager(container: AppContainer = Depends(get_container)) -> CrManagerService:
    return container.cr_manager_service


def to_task_response(task: CrManagerTask) -> CrManagerTaskResponse:
    return CrManagerTaskResponse(
        task_id=task.task_id,
        order_id=task.order_id,
        source_id=task.source_id,
        correlation_id=task.correlation_id,
        agent_run_id=task.agent_run_id,
        status=task.status.value,
        failed_criteria=task.failed_criteria,
        attempt=task.attempt,
        action=task.action,
        jira_issue_id=task.jira_issue_id,
        jira_issue_url=task.jira_issue_url,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


@router.post("/task", response_model=CrManagerTaskResponse)
async def create_task(
    request: DispatchCrTaskRequest,
    cr_manager: CrManagerService = Depends(get_cr_manager),
) -> CrManagerTaskResponse:
    task = await cr_manager.create_task(request)
    return to_task_response(task)


@router.get("/task/{task_id}", response_model=CrManagerTaskResponse)
async def get_task(
    task_id: str,
    cr_manager: CrManagerService = Depends(get_cr_manager),
) -> CrManagerTaskResponse:
    try:
        task = await cr_manager.get_task(task_id)
    except CrManagerTaskNotFound as exc:
        raise HTTPException(status_code=404, detail="CR Manager task not found") from exc
    return to_task_response(task)
