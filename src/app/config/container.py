from __future__ import annotations

from functools import lru_cache

from agents.coordinator.adapters.in_memory.order_repository import InMemoryOrderRepository
from agents.coordinator.adapters.in_memory.task_repository import InMemoryTaskRepository
from agents.coordinator.adapters.in_memory.trace import InMemoryTraceAdapter
from agents.coordinator.adapters.in_process.cr_manager import InProcessCrManagerAdapter
from agents.coordinator.adapters.mock.replica_init import MockReplicaInitAdapter
from agents.coordinator.adapters.mock.warp import MockWarpAdapter
from agents.coordinator.application.service import CoordinatorService
from agents.cr_manager.adapters.in_memory.task_repository import (
    InMemoryCrManagerTaskRepository,
)
from agents.cr_manager.adapters.mock.jira import MockJiraAdapter
from agents.cr_manager.adapters.mock.warp import MockWarpRemediationAdapter
from agents.cr_manager.application.service import CrManagerService
from app.config.settings import AdapterProfile, Settings, load_settings


class AppContainer:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or load_settings()
        self.orders = InMemoryOrderRepository()
        self.tasks = InMemoryTaskRepository()
        self.cr_manager_tasks = InMemoryCrManagerTaskRepository()
        self.trace = InMemoryTraceAdapter()
        self.llm = self._build_llm()
        self.jira = self._build_jira()
        self.cr_manager_warp = self._build_cr_manager_warp()
        self.warp = self._build_warp()
        self.replica_init = self._build_replica_init()
        self.cr_manager_service = CrManagerService(
            tasks=self.cr_manager_tasks,
            jira=self.jira,
            warp=self.cr_manager_warp,
            trace=self.trace,
        )
        self.cr_manager = self._build_cr_manager()
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
            return InProcessCrManagerAdapter(self.cr_manager_service)
        raise NotImplementedError("HTTP CR Manager adapter is not implemented yet")

    def _build_replica_init(self):
        if self.settings.adapter_profile == AdapterProfile.MOCK:
            return MockReplicaInitAdapter()
        raise NotImplementedError("HTTP Replica Init adapter is not implemented yet")

    def _build_jira(self):
        if self.settings.adapter_profile == AdapterProfile.MOCK:
            return MockJiraAdapter()
        raise NotImplementedError("HTTP Jira adapter is not implemented yet")

    def _build_cr_manager_warp(self):
        if self.settings.adapter_profile == AdapterProfile.MOCK:
            return MockWarpRemediationAdapter()
        raise NotImplementedError("HTTP WARP remediation adapter is not implemented yet")

    def _build_llm(self):
        if not self.settings.gigachat_auth_token:
            return None
        from shared.adapters.llm.gigachat import GigaChatAdapter, GigaChatAdapterConfig

        return GigaChatAdapter(
            GigaChatAdapterConfig(
                auth_token=self.settings.gigachat_auth_token,
                scope=self.settings.gigachat_scope,
                model=self.settings.gigachat_model,
                embeddings_model=self.settings.gigachat_embeddings_model,
                oauth_url=self.settings.gigachat_oauth_url,
                chat_url=self.settings.gigachat_chat_url,
                embeddings_url=self.settings.gigachat_embeddings_url,
                timeout_seconds=self.settings.gigachat_timeout_seconds,
                verify_ssl=self.settings.gigachat_verify_ssl,
                ca_bundle_path=self.settings.gigachat_ca_bundle_path,
            )
        )


@lru_cache
def get_container() -> AppContainer:
    return AppContainer()
