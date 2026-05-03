from __future__ import annotations

from agents.cr_manager.domain.statuses import CrManagerTaskStatus
from agents.cr_manager.domain.task import CrManagerTask
from agents.cr_manager.ports.jira import CreateJiraIssueRequest, JiraPort
from agents.cr_manager.ports.task_repository import CrManagerTaskRepositoryPort
from agents.cr_manager.ports.trace import TracePort
from agents.cr_manager.ports.warp import (
    GetWarpRemediationRequest,
    RemediationCriterion,
    WarpRemediationPort,
)
from shared.contracts.tasks import DispatchCrTaskRequest
from shared.contracts.trace import TraceEvent
from shared.domain.ids import new_agent_run_id, new_task_id


class CrManagerTaskNotFound(LookupError):
    pass


class CrManagerService:
    def __init__(
        self,
        *,
        tasks: CrManagerTaskRepositoryPort,
        jira: JiraPort,
        warp: WarpRemediationPort,
        trace: TracePort,
    ) -> None:
        self.tasks = tasks
        self.jira = jira
        self.warp = warp
        self.trace = trace

    async def create_task(self, request: DispatchCrTaskRequest) -> CrManagerTask:
        idempotency_key = request.idempotency_key or self._build_idempotency_key(request)
        existing = await self.tasks.get_by_idempotency_key(idempotency_key)
        if existing is not None:
            await self._trace(
                existing,
                "cr_task_duplicate_ignored",
                {"idempotency_key": idempotency_key},
            )
            return existing

        task = CrManagerTask(
            task_id=new_task_id(),
            order_id=request.order_id,
            source_id=request.source_id,
            correlation_id=request.correlation_id,
            agent_run_id=new_agent_run_id(),
            failed_criteria=list(request.failed_criteria),
            failed_items=[item.model_dump() for item in request.failed_items],
            load_plan=request.load_plan,
            warp_check_id=request.warp_check_id,
            attempt=request.attempt,
            action=request.action,
            idempotency_key=idempotency_key,
        )
        await self.tasks.save(task)
        await self._trace(
            task,
            "cr_task_received",
            {
                "order_id": task.order_id,
                "source_id": task.source_id,
                "attempt": task.attempt,
                "action": task.action,
                "failed_criteria": task.failed_criteria,
                "failed_items": task.failed_items,
                "load_plan": task.load_plan,
                "warp_check_id": task.warp_check_id,
            },
        )
        await self._get_warp_remediation(task)
        await self._create_jira_issue(task)
        return task

    async def get_task(self, task_id: str) -> CrManagerTask:
        task = await self.tasks.get(task_id)
        if task is None:
            raise CrManagerTaskNotFound(task_id)
        return task

    async def list_tasks(self, correlation_id: str) -> list[CrManagerTask]:
        return await self.tasks.list_by_correlation_id(correlation_id)

    async def _trace(self, task: CrManagerTask, action: str, payload: dict) -> None:
        await self.trace.write(
            TraceEvent(
                correlation_id=task.correlation_id,
                agent="cr-manager",
                action=action,
                payload={
                    "task_id": task.task_id,
                    "agent_run_id": task.agent_run_id,
                    **payload,
                },
            )
        )

    async def _create_jira_issue(self, task: CrManagerTask) -> None:
        summary = self._build_jira_summary(task)
        description = self._build_jira_description(task)
        result = await self.jira.create_issue(
            CreateJiraIssueRequest(
                idempotency_key=task.idempotency_key,
                task_id=task.task_id,
                order_id=task.order_id,
                source_id=task.source_id,
                correlation_id=task.correlation_id,
                summary=summary,
                description=description,
                failed_criteria=list(task.failed_criteria),
                failed_items=list(task.failed_items),
                remediation_items=list(task.remediation_items),
                load_plan=task.load_plan,
                warp_check_id=task.warp_check_id,
                attempt=task.attempt,
                action=task.action,
            )
        )
        task.jira_issue_id = result.issue_id
        task.jira_issue_url = result.issue_url
        task.jira_summary = result.summary
        task.jira_description = result.description
        task.status = CrManagerTaskStatus.JIRA_CREATED
        task.touch()
        await self.tasks.save(task)
        await self._trace(
            task,
            "jira_issue_created",
            {
                "jira_issue_id": result.issue_id,
                "jira_issue_url": result.issue_url,
                "created": result.created,
                "idempotency_key": task.idempotency_key,
                "summary": result.summary,
            },
        )

    async def _get_warp_remediation(self, task: CrManagerTask) -> None:
        result = await self.warp.get_remediation(
            GetWarpRemediationRequest(
                source_id=task.source_id,
                correlation_id=task.correlation_id,
                criteria=self._remediation_criteria(task),
                load_plan=task.load_plan,
                warp_check_id=task.warp_check_id,
            )
        )
        task.remediation_items = [item.to_dict() for item in result.items]
        task.status = CrManagerTaskStatus.REMEDIATION_RECEIVED
        task.touch()
        await self.tasks.save(task)
        await self._trace(
            task,
            "remediation_received",
            {
                "load_plan": task.load_plan,
                "warp_check_id": task.warp_check_id,
                "items": task.remediation_items,
            },
        )

    def _build_idempotency_key(self, request: DispatchCrTaskRequest) -> str:
        legacy_criteria = ",".join(sorted(request.failed_criteria))
        structured_criteria = ",".join(
            sorted(
                f"{item.criteria_id}:{','.join(sorted(item.failed_params))}"
                for item in request.failed_items
            )
        )
        return (
            f"cr-manager:{request.order_id}:{request.source_id}:"
            f"{request.correlation_id}:{request.attempt}:{request.action}:"
            f"{request.load_plan}:{request.warp_check_id}:"
            f"{legacy_criteria}:{structured_criteria}"
        )

    def _remediation_criteria(self, task: CrManagerTask) -> list[RemediationCriterion]:
        if task.failed_items:
            return [
                RemediationCriterion(
                    criteria_id=str(item["criteria_id"]),
                    param_ids=list(item.get("failed_params", [])),
                )
                for item in task.failed_items
            ]
        return [self._legacy_criterion(value) for value in task.failed_criteria]

    def _legacy_criterion(self, value: str) -> RemediationCriterion:
        if "." not in value:
            return RemediationCriterion(criteria_id=value)
        criteria_id, param_id = value.split(".", 1)
        return RemediationCriterion(criteria_id=criteria_id, param_ids=[param_id])

    def _build_jira_summary(self, task: CrManagerTask) -> str:
        return f"[DREAM] Remediation {task.source_id} attempt {task.attempt}"

    def _build_jira_description(self, task: CrManagerTask) -> str:
        lines = [
            f"Источник: {task.source_id}",
            f"Предзаказ: {task.order_id}",
            f"Correlation: {task.correlation_id}",
            f"Попытка: {task.attempt}",
        ]
        if task.load_plan:
            lines.append(f"План проверки: {task.load_plan}")
        if task.warp_check_id:
            lines.append(f"WARP check: {task.warp_check_id}")
        lines.extend(["", "Не выполнено:"])
        if task.failed_items:
            for item in task.failed_items:
                params = ", ".join(item.get("failed_params", [])) or "-"
                lines.append(f"- {item['criteria_id']}: параметры {params}")
        else:
            for criterion in task.failed_criteria:
                lines.append(f"- {criterion}")
        lines.extend(["", "Remediation-инструкции:"])
        for item in task.remediation_items:
            label = item["criteria_id"]
            if item.get("param_id"):
                label = f"{label}/{item['param_id']}"
            lines.append(f"- {label}: {item['title']}")
            for index, step in enumerate(item["steps"], start=1):
                lines.append(f"  {index}. {step}")
        return "\n".join(lines)
