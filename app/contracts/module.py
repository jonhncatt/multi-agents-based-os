from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from app.contracts.health import HealthReport
from app.contracts.manifest import ModuleManifest
from app.contracts.provider_contract import ProviderContract
from app.contracts.task import TaskRequest, TaskResponse
from app.contracts.tool import ToolCall, ToolResult


@runtime_checkable
class BaseModule(Protocol):
    manifest: ModuleManifest

    def init(self, kernel_context: Any) -> None: ...

    def health_check(self) -> HealthReport: ...

    def shutdown(self) -> None: ...


@runtime_checkable
class BaseSystemModule(BaseModule, Protocol):
    pass


@runtime_checkable
class BaseBusinessModule(BaseModule, Protocol):
    def invoke(self, request: TaskRequest) -> TaskResponse: ...


@runtime_checkable
class BaseToolProvider(Protocol):
    provider_id: str
    supported_tools: list[str]

    def execute(self, call: ToolCall) -> ToolResult: ...

    def health_check(self) -> HealthReport: ...


def provider_contract_from_instance(provider: BaseToolProvider) -> ProviderContract:
    contract = getattr(provider, "provider_contract", None)
    if isinstance(contract, ProviderContract):
        return contract
    return ProviderContract(
        provider_id=str(getattr(provider, "provider_id", "") or "").strip(),
        supported_tools=list(getattr(provider, "supported_tools", []) or []),
        degraded_behavior="fallback_or_degrade",
    )
