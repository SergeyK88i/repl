from __future__ import annotations

from enum import Enum


class CrManagerTaskStatus(str, Enum):
    RECEIVED = "RECEIVED"
    JIRA_CREATED = "JIRA_CREATED"
    REMEDIATION_RECEIVED = "REMEDIATION_RECEIVED"
    EXECUTING = "EXECUTING"
    SELF_CHECKING = "SELF_CHECKING"
    DONE = "DONE"
    FAILED = "FAILED"
    ESCALATED = "ESCALATED"
