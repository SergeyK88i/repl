from __future__ import annotations

from uuid import uuid4

from shared.contracts.readiness import (
    ReadinessCheckRequest,
    ReadinessCheckResult,
    ReadinessContext,
    ReadinessScore,
    ReadinessStatus,
)
from shared.contracts.trace import TraceEvent


class MockWarpAdapter:
    def __init__(self, trace=None) -> None:
        self.trace = trace

    async def check_readiness(self, request: ReadinessCheckRequest) -> ReadinessCheckResult:
        await self._trace(
            request,
            "readiness_check_started",
            {"context": request.context.value, "source_id": request.source_id},
        )
        source = request.source_id.lower()

        if "ready" in source:
            result = ReadinessCheckResult(
                status=ReadinessStatus.READY,
                score=ReadinessScore(current=40, required=40),
                audit_hash=f"mock-{uuid4().hex[:8]}",
            )
            await self._trace_result(request, result)
            return result

        if request.context == ReadinessContext.FINAL_CHECK and "fail" not in source:
            result = ReadinessCheckResult(
                status=ReadinessStatus.READY,
                score=ReadinessScore(current=40, required=40),
                audit_hash=f"mock-{uuid4().hex[:8]}",
            )
            await self._trace_result(request, result)
            return result

        failed_criteria = ["C1", "C3.P2"] if "fail" not in source else ["C5"]
        result = ReadinessCheckResult(
            status=ReadinessStatus.NOT_READY,
            score=ReadinessScore(current=12, required=40),
            failed_criteria=failed_criteria,
            regression="fail" in source and request.context == ReadinessContext.FINAL_CHECK,
        )
        await self._trace_result(request, result)
        return result

    async def _trace_result(
        self,
        request: ReadinessCheckRequest,
        result: ReadinessCheckResult,
    ) -> None:
        await self._trace(
            request,
            "readiness_check_finished",
            {
                "context": request.context.value,
                "source_id": request.source_id,
                "status": result.status.value,
                "score": result.score.model_dump() if result.score else None,
                "failed_criteria": result.failed_criteria,
                "audit_hash": result.audit_hash,
                "regression": result.regression,
            },
        )

    async def _trace(
        self,
        request: ReadinessCheckRequest,
        action: str,
        payload: dict,
    ) -> None:
        if self.trace is None:
            return
        await self.trace.write(
            TraceEvent(
                correlation_id=request.correlation_id,
                agent="warp",
                action=action,
                payload=payload,
            )
        )
