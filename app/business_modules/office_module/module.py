from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

from app.business_modules.office_module.manifest import OFFICE_MODULE_COMPATIBILITY_SHIMS, OFFICE_MODULE_MANIFEST
from app.business_modules.office_module.pipeline.runtime import build_office_pipeline_trace
from app.business_modules.office_module.policies.catalog import OFFICE_MODULE_POLICY_SET
from app.business_modules.office_module.workflow import ROLE_CHAIN, build_office_workflow_plan
from app.contracts import HealthReport, TaskRequest, TaskResponse
from app.kernel.runtime_context import RuntimeContext
from app.models import ChatSettings


class OfficeModule:
    """Standard business-module entrypoint.

    The execution core still relies on the legacy OfficeAgent runtime for now.
    This module is the formal business-module surface and is treated as the
    compatibility boundary for legacy orchestration logic.
    """

    manifest = OFFICE_MODULE_MANIFEST

    def __init__(
        self,
        *,
        config: Any,
        legacy_host: Any | None = None,
        kernel_runtime: Any | None = None,
    ) -> None:
        self._config = config
        self._kernel_context: Any = None
        self._legacy_host = legacy_host
        self._kernel_runtime = kernel_runtime
        self._agent: Any | None = None

    def init(self, kernel_context: Any) -> None:
        self._kernel_context = kernel_context

    def bind_legacy_host(self, legacy_host: Any) -> None:
        self._legacy_host = legacy_host

    def _runtime(self) -> Any:
        if self._legacy_host is not None:
            return self._legacy_host
        if self._agent is None:
            from app.agent import OfficeAgent

            self._agent = OfficeAgent(self._config, kernel_runtime=self._kernel_runtime)
        return self._agent

    def health_check(self) -> HealthReport:
        return HealthReport(
            component_id=self.manifest.module_id,
            status="healthy",
            summary="office module active",
            details={
                "roles": list(ROLE_CHAIN),
                "compatibility_level": self.manifest.compatibility_level,
                "required_tools": list(self.manifest.required_tools),
                "optional_tools": list(self.manifest.optional_tools),
            },
        )

    def shutdown(self) -> None:
        self._agent = None

    def handle(self, request: TaskRequest, context: RuntimeContext) -> TaskResponse:
        runtime = self._runtime()
        request_context = dict(request.context or {})
        context.selected_roles = list(context.selected_roles or ROLE_CHAIN)
        context.selected_tools = list(context.selected_tools or [*self.manifest.required_tools, *self.manifest.optional_tools])
        context.metadata.setdefault("compatibility_shims", list(OFFICE_MODULE_COMPATIBILITY_SHIMS))
        context.metadata.setdefault("policy_set", list(OFFICE_MODULE_POLICY_SET))
        try:
            settings_obj = self._normalize_settings(request.settings)
            run = runtime.run_chat(
                request_context.get("history_turns") or [],
                str(request_context.get("summary") or ""),
                request.message,
                request.attachments,
                settings_obj,
                session_id=request_context.get("session_id"),
                route_state=request_context.get("route_state") if isinstance(request_context.get("route_state"), dict) else None,
                progress_cb=request_context.get("progress_cb"),
            )
            payload = self._normalize_run_payload(run)
            payload["module_id"] = self.manifest.module_id
            payload["selected_roles"] = list(context.selected_roles)
            payload["selected_tools"] = list(context.selected_tools)
            payload["selected_providers"] = list(context.selected_providers)
            payload["compatibility_shims"] = list(OFFICE_MODULE_COMPATIBILITY_SHIMS)
            payload["module_pipeline"] = build_office_pipeline_trace(
                active_roles=payload.get("active_roles"),
                current_role=payload.get("current_role"),
            )
            return TaskResponse(
                ok=True,
                task_id=request.task_id,
                text=str(payload.get("text") or ""),
                payload=payload,
            )
        except Exception as exc:
            context.health_state = "degraded"
            return TaskResponse(
                ok=False,
                task_id=request.task_id,
                error=str(exc),
                warnings=["office_module handle failed"],
            )

    def invoke(self, request: TaskRequest) -> TaskResponse:
        return self.handle(request, RuntimeContext(request_id=request.task_id, module_id=self.manifest.module_id))

    def run_chat(
        self,
        history_turns: list[dict[str, Any]],
        summary: str,
        user_message: str,
        attachment_metas: list[dict[str, Any]],
        settings: Any,
        *,
        session_id: str | None = None,
        route_state: dict[str, Any] | None = None,
        progress_cb: Any | None = None,
    ) -> Any:
        runtime = self._runtime()
        return runtime.run_chat(
            history_turns,
            summary,
            user_message,
            attachment_metas,
            self._normalize_settings(settings),
            session_id=session_id,
            route_state=route_state,
            progress_cb=progress_cb,
        )

    def workflow_plan(self) -> list[str]:
        return build_office_workflow_plan()

    def _normalize_settings(self, value: Any) -> ChatSettings:
        if isinstance(value, ChatSettings):
            return value
        if is_dataclass(value):
            value = asdict(value)
        if isinstance(value, dict):
            payload = dict(value)
            try:
                return ChatSettings(**payload)
            except Exception:
                pass
        return ChatSettings()

    def _normalize_run_payload(self, run: Any) -> dict[str, Any]:
        if not isinstance(run, tuple):
            return {"text": str(run or ""), "raw": run}
        fields = (
            "text",
            "tool_events",
            "attachment_note",
            "execution_plan",
            "execution_trace",
            "pipeline_hooks",
            "debug_flow",
            "agent_panels",
            "active_roles",
            "current_role",
            "role_states",
            "answer_bundle",
            "usage_total",
            "effective_model",
            "route_state",
        )
        return {name: (run[idx] if idx < len(run) else None) for idx, name in enumerate(fields)}
