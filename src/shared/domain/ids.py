from __future__ import annotations

from uuid import uuid4


def new_order_id() -> str:
    return f"ORD-{uuid4().hex[:12].upper()}"


def new_task_id() -> str:
    return f"TASK-{uuid4().hex[:12].upper()}"


def new_correlation_id() -> str:
    return f"CORR-{uuid4().hex}"


def new_agent_run_id() -> str:
    return f"RUN-{uuid4().hex[:12].upper()}"

