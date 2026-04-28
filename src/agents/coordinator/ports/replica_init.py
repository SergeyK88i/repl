from __future__ import annotations

from typing import Protocol

from shared.contracts.replica import ReplicaInitRequest, ReplicaInitResult


class ReplicaInitPort(Protocol):
    async def start(self, request: ReplicaInitRequest) -> ReplicaInitResult:
        ...

