from __future__ import annotations

from shared.contracts.replica import ReplicaInitRequest, ReplicaInitResult


class MockReplicaInitAdapter:
    def __init__(self) -> None:
        self.started: list[ReplicaInitRequest] = []

    async def start(self, request: ReplicaInitRequest) -> ReplicaInitResult:
        self.started.append(request)
        return ReplicaInitResult(
            accepted=True,
            replica_job_id=f"REPLICA-{request.order_id}",
        )

