from __future__ import annotations

from agents.cr_manager.ports.warp import (
    GetWarpRemediationRequest,
    GetWarpRemediationResult,
    RemediationItem,
)


class MockWarpRemediationAdapter:
    async def get_remediation(
        self,
        request: GetWarpRemediationRequest,
    ) -> GetWarpRemediationResult:
        items: list[RemediationItem] = []
        for criterion in request.criteria:
            if not criterion.param_ids:
                items.append(self._item_for(criterion.criteria_id, None))
                continue
            for param_id in criterion.param_ids:
                items.append(self._item_for(criterion.criteria_id, param_id))
        return GetWarpRemediationResult(items=items)

    def _item_for(self, criteria_id: str, param_id: str | None) -> RemediationItem:
        label = criteria_id if param_id is None else f"{criteria_id}/{param_id}"
        return RemediationItem(
            criteria_id=criteria_id,
            param_id=param_id,
            title=f"Закрыть критерий {label}",
            steps=[
                f"Открыть карточку источника для проверки {label}",
                "Выполнить remediation-инструкцию WARP",
                "Сохранить изменения и подготовить self-check",
            ],
            recommended_owner="source_team",
            recommended_connector="manual_review",
            automation_possible=False,
            required_inputs=["source_id"],
            expected_result=f"Критерий {label} выполнен",
        )
