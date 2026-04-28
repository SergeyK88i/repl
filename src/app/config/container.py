from __future__ import annotations

from functools import lru_cache

from agents.coordinator.adapters.in_memory.order_repository import InMemoryOrderRepository
from agents.coordinator.adapters.in_memory.task_repository import InMemoryTaskRepository
from agents.coordinator.adapters.in_memory.trace import InMemoryTraceAdapter
from agents.coordinator.adapters.mock.cr_manager import MockCrManagerAdapter
from agents.coordinator.adapters.mock.replica_init import MockReplicaInitAdapter
from agents.coordinator.adapters.mock.warp import MockWarpAdapter
from agents.coordinator.application.service import CoordinatorService
from app.config.settings import AdapterProfile, Settings, load_settings


class AppContainer:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or load_settings()
        self.orders = InMemoryOrderRepository()
        self.tasks = InMemoryTaskRepository()
        self.trace = InMemoryTraceAdapter()
        self.warp = self._build_warp()
        self.cr_manager = self._build_cr_manager()
        self.replica_init = self._build_replica_init()
        self.coordinator = CoordinatorService(
            orders=self.orders,
            tasks=self.tasks,
            warp=self.warp,
            cr_manager=self.cr_manager,
            replica_init=self.replica_init,
            trace=self.trace,
            max_attempts=self.settings.max_attempts,
        )

    def _build_warp(self):
        if self.settings.adapter_profile == AdapterProfile.MOCK:
            return MockWarpAdapter(trace=self.trace)
        raise NotImplementedError("HTTP WARP adapter is not implemented yet")

    def _build_cr_manager(self):
        if self.settings.adapter_profile == AdapterProfile.MOCK:
            return MockCrManagerAdapter(trace=self.trace)
        raise NotImplementedError("HTTP CR Manager adapter is not implemented yet")

    def _build_replica_init(self):
        if self.settings.adapter_profile == AdapterProfile.MOCK:
            return MockReplicaInitAdapter()
        raise NotImplementedError("HTTP Replica Init adapter is not implemented yet")


@lru_cache
def get_container() -> AppContainer:
    return AppContainer()
