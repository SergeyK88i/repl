from __future__ import annotations

from shared.contracts.trace import TraceEvent


class InMemoryTraceAdapter:
    def __init__(self) -> None:
        self._events: list[TraceEvent] = []

    async def write(self, event: TraceEvent) -> None:
        self._events.append(event)

    async def list_by_correlation_id(self, correlation_id: str) -> list[TraceEvent]:
        return [event for event in self._events if event.correlation_id == correlation_id]

