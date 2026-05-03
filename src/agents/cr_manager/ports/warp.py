from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True, slots=True)
class RemediationCriterion:
    criteria_id: str
    param_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class GetWarpRemediationRequest:
    source_id: str
    correlation_id: str
    criteria: list[RemediationCriterion]
    load_plan: str | None = None
    warp_check_id: str | None = None


@dataclass(frozen=True, slots=True)
class RemediationItem:
    criteria_id: str
    param_id: str | None
    title: str
    steps: list[str]
    recommended_owner: str | None = None
    recommended_connector: str | None = None
    automation_possible: bool = False
    required_inputs: list[str] = field(default_factory=list)
    expected_result: str | None = None

    def to_dict(self) -> dict:
        return {
            "criteria_id": self.criteria_id,
            "param_id": self.param_id,
            "title": self.title,
            "steps": list(self.steps),
            "recommended_owner": self.recommended_owner,
            "recommended_connector": self.recommended_connector,
            "automation_possible": self.automation_possible,
            "required_inputs": list(self.required_inputs),
            "expected_result": self.expected_result,
        }


@dataclass(frozen=True, slots=True)
class GetWarpRemediationResult:
    items: list[RemediationItem]


class WarpRemediationPort(Protocol):
    async def get_remediation(
        self,
        request: GetWarpRemediationRequest,
    ) -> GetWarpRemediationResult:
        ...
