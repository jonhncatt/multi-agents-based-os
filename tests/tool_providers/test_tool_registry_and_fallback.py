from __future__ import annotations

from app.contracts import ToolCall, ToolContract
from app.kernel.host import KernelHost
from tests.support_agent_os import BrokenWorkspaceProvider, HealthyWorkspaceProvider


def test_primary_provider_failure_uses_fallback_provider() -> None:
    kernel = KernelHost()
    kernel.registry.register_tool_contract(
        ToolContract(tool_id="workspace.read", timeout=0.1, retry_policy={"max_retries": 0}, permission_scope="workspace:read"),
        primary_provider="broken_workspace_provider",
    )
    kernel.register_provider(BrokenWorkspaceProvider())
    kernel.register_provider(HealthyWorkspaceProvider())

    result = kernel.tool_bus.execute(ToolCall(name="workspace.read"))

    assert result.ok is True
    assert result.fallback_used is True
    assert result.provider_id == "healthy_workspace_provider"


def test_repeated_provider_failures_open_simple_circuit() -> None:
    kernel = KernelHost()
    kernel.registry.register_tool_contract(
        ToolContract(tool_id="workspace.read", timeout=0.1, retry_policy={"max_retries": 0}, permission_scope="workspace:read"),
        primary_provider="broken_workspace_provider",
    )
    kernel.register_provider(BrokenWorkspaceProvider())
    kernel.register_provider(HealthyWorkspaceProvider())

    for _ in range(3):
        kernel.tool_bus.execute(ToolCall(name="workspace.read"))

    state = kernel.registry.providers.state("broken_workspace_provider")
    assert state.status == "degraded"
    assert state.circuit_open is True
