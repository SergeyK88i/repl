from __future__ import annotations

from typing import Protocol

from shared.contracts.trace import TraceEvent


class TracePort(Protocol):
    async def write(self, event: TraceEvent) -> None:
        ...

    async def list_by_correlation_id(self, correlation_id: str) -> list[TraceEvent]:
        ...
