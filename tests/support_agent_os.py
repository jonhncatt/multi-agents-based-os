from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.contracts import HealthReport, ModuleManifest, TaskRequest, TaskResponse, ToolCall, ToolResult


class DummyLegacyHost:
    def __init__(self, text: str = "dummy response") -> None:
        self._text = text

    def run_chat(self, *args: Any, **kwargs: Any) -> tuple[Any, ...]:
        _ = args, kwargs
        return (
            self._text,
            [],
            "",
            ["router", "planner", "worker"],
            ["trace:office_module"],
            [],
            [],
            [],
            ["router", "planner", "worker"],
            "worker",
            [],
            {},
            {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2, "llm_calls": 1},
            "gpt-test",
            {"top_intent": "understanding"},
        )


@dataclass
class EchoBusinessModule:
    manifest: ModuleManifest
    text: str
    healthy: bool = True

    def init(self, kernel_context: Any) -> None:
        self._kernel_context = kernel_context

    def health_check(self) -> HealthReport:
        return HealthReport(
            component_id=self.manifest.module_id,
            status="healthy" if self.healthy else "unhealthy",
            summary="ok" if self.healthy else "bad",
        )

    def shutdown(self) -> None:
        return None

    def handle(self, request: TaskRequest, context: Any) -> TaskResponse:
        return TaskResponse(ok=True, task_id=request.task_id, text=self.text, payload={"module_id": self.manifest.module_id})

    def invoke(self, request: TaskRequest) -> TaskResponse:
        return self.handle(request, None)


class BrokenWorkspaceProvider:
    provider_id = "broken_workspace_provider"
    supported_tools = ["workspace.read"]

    def execute(self, call: ToolCall) -> ToolResult:
        raise RuntimeError(f"boom:{call.name}")

    def health_check(self) -> HealthReport:
        return HealthReport(component_id=self.provider_id, status="healthy", summary="ok")


class HealthyWorkspaceProvider:
    provider_id = "healthy_workspace_provider"
    supported_tools = ["workspace.read"]

    def execute(self, call: ToolCall) -> ToolResult:
        return ToolResult(ok=True, tool_name=call.name, provider_id=self.provider_id, data={"ok": True, "value": 1})

    def health_check(self) -> HealthReport:
        return HealthReport(component_id=self.provider_id, status="healthy", summary="ok")
