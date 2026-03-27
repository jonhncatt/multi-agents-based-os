from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import logging
import os
import threading
import time
from typing import Any

from app.contracts import BaseBusinessModule, BaseModule, BaseToolProvider, TaskRequest, TaskResponse
from app.kernel.compatibility import CompatibilityChecker
from app.kernel.event_bus import EventBus
from app.kernel.health import HealthManager
from app.kernel.lifecycle import LifecycleManager
from app.kernel.registry import ModuleRegistry
from app.kernel.rollback import RollbackManager
from app.kernel.runtime_context import RuntimeContext
from app.kernel.tool_bus import ToolBus
from app.kernel.trace import KernelExecutionTrace, TraceEvent


@dataclass(slots=True)
class KernelContextView:
    kernel_version: str
    registry: ModuleRegistry
    tool_bus: ToolBus
    event_bus: EventBus

    @property
    def tool_registry(self):
        return self.registry.tools

    @property
    def provider_registry(self):
        return self.registry.providers

    def lookup_module(self, module_id: str) -> BaseModule | None:
        return self.registry.get_module(module_id)


class KernelHost:
    def __init__(
        self,
        *,
        kernel_version: str = "1.0.0",
        registry: ModuleRegistry | None = None,
        lifecycle: LifecycleManager | None = None,
        event_bus: EventBus | None = None,
        tool_bus: ToolBus | None = None,
        compatibility: CompatibilityChecker | None = None,
        health_manager: HealthManager | None = None,
        rollback_manager: RollbackManager | None = None,
        trace_dir: str | None = None,
    ) -> None:
        self.kernel_version = str(kernel_version or "1.0.0").strip() or "1.0.0"
        self.registry = registry or ModuleRegistry()
        self.event_bus = event_bus or EventBus()
        self.lifecycle = lifecycle or LifecycleManager()
        self.compatibility = compatibility or CompatibilityChecker(kernel_version=self.kernel_version)
        self.tool_bus = tool_bus or ToolBus(self.registry, event_bus=self.event_bus)
        self.health_manager = health_manager or HealthManager()
        self.rollback_manager = rollback_manager or RollbackManager()
        self._initialized = False
        self._recent_traces: list[dict[str, object]] = []
        self._trace_local = threading.local()
        self._trace_dir = Path(trace_dir or "artifacts/agent_os_traces").resolve()
        self._trace_enabled = bool(int(str(os.environ.get("AGENT_OS_TRACE", "0") or "0")))
        self._trace_verbose = bool(int(str(os.environ.get("AGENT_OS_TRACE_VERBOSE", "0") or "0")))
        self._logger = logging.getLogger("agent_os.kernel")
        for event_name in (
            "module_registered",
            "provider_registered",
            "tool_dispatch",
            "tool_result",
            "tool_fallback",
            "provider_failed",
            "provider_circuit_open",
            "provider_skipped",
        ):
            self.event_bus.subscribe(event_name, self._capture_event)

    @property
    def context(self) -> KernelContextView:
        return KernelContextView(
            kernel_version=self.kernel_version,
            registry=self.registry,
            tool_bus=self.tool_bus,
            event_bus=self.event_bus,
        )

    def load_modules(self, modules: list[BaseModule] | None = None) -> list[str]:
        loaded: list[str] = []
        for module in modules or []:
            self.register_module(module)
            loaded.append(module.manifest.module_id)
        self.init()
        return loaded

    def register_module(self, module: BaseModule) -> None:
        self.compatibility.assert_manifest_compatible(module.manifest)
        self.registry.register_module(module)
        if self._initialized:
            self.lifecycle.init_module(module, kernel_context=self.context)
            self.registry.mark_module_state(module.manifest.module_id, lifecycle="ready")
        self.event_bus.publish("module_registered", {"module_id": module.manifest.module_id, "version": module.manifest.version})

    def register_provider(self, provider: BaseToolProvider) -> None:
        self.registry.register_provider(provider)
        self.event_bus.publish("provider_registered", {"provider_id": provider.provider_id})

    def init(self) -> None:
        if self._initialized:
            return
        modules = self.registry.list_modules()
        self.lifecycle.init_modules(list(modules), kernel_context=self.context)
        for module in modules:
            self.registry.mark_module_state(module.manifest.module_id, lifecycle="ready")
        self._initialized = True
        self.health_manager.startup_check(self.registry)
        self.event_bus.publish("kernel_initialized", {"module_count": len(modules)})

    def shutdown(self) -> None:
        self.lifecycle.shutdown_all()
        for module in self.registry.list_modules():
            self.registry.mark_module_state(module.manifest.module_id, lifecycle="disabled")
        self._initialized = False
        self.event_bus.publish("kernel_shutdown", {})

    def resolve_module(self, request: TaskRequest, module_id: str | None = None) -> BaseBusinessModule | None:
        explicit = str(module_id or request.context.get("module_id") or "").strip()
        if explicit:
            return self.registry.get_business_module(explicit)
        task_type = str(request.task_type or "").strip().lower()
        mapping = {
            "chat": "office_module",
            "task.chat": "office_module",
            "office": "office_module",
            "task.office": "office_module",
            "research": "research_module",
            "task.research": "research_module",
            "coding": "coding_module",
            "task.coding": "coding_module",
            "adaptation": "adaptation_module",
            "task.adaptation": "adaptation_module",
        }
        resolved = mapping.get(task_type, "office_module")
        return self.registry.get_business_module(resolved)

    def inject_tools_and_providers(self, module: BaseModule) -> dict[str, object]:
        manifest = module.manifest
        selected_tools = [*manifest.required_tools, *manifest.optional_tools]
        selected_providers = [
            item.provider_id
            for tool_name in selected_tools
            for item in self.registry.providers_for_tool(tool_name)
        ]
        return {
            "required_tools": list(manifest.required_tools),
            "optional_tools": list(manifest.optional_tools),
            "selected_tools": selected_tools,
            "selected_providers": selected_providers,
            "required_system_modules": list(manifest.required_system_modules),
        }

    def run_module(self, module: BaseBusinessModule, request: TaskRequest, context: RuntimeContext) -> TaskResponse:
        self.registry.mark_module_state(module.manifest.module_id, lifecycle="ready")
        handler = getattr(module, "handle", None)
        try:
            if callable(handler):
                response = handler(request, context)
            else:
                response = module.invoke(request)
        except Exception as exc:
            self.registry.mark_module_state(module.manifest.module_id, lifecycle="degraded", error=str(exc))
            context.health_state = "degraded"
            return TaskResponse(ok=False, task_id=request.task_id, error=str(exc), warnings=["kernel isolated module failure"])
        return response

    def observe_and_record(self, trace: KernelExecutionTrace) -> None:
        payload = trace.to_dict(verbose=self._trace_verbose)
        self._recent_traces.append(payload)
        self._recent_traces = self._recent_traces[-20:]
        self._logger.info("agent_os_trace %s", json.dumps(payload, ensure_ascii=False))
        if self._trace_enabled:
            self._trace_dir.mkdir(parents=True, exist_ok=True)
            path = self._trace_dir / f"{trace.request_id}.json"
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def fallback_or_rollback(self, module_id: str, *, error: str = "") -> dict[str, object]:
        if error:
            self.registry.mark_module_state(module_id, lifecycle="degraded", error=error)
        rollback = self.rollback_manager.rollback_module(self.registry, module_id)
        if rollback.get("ok"):
            self.event_bus.publish("module_rolled_back", rollback)
        return rollback

    def dispatch(self, request: TaskRequest, *, module_id: str | None = None) -> TaskResponse:
        started = time.perf_counter()
        module = self.resolve_module(request, module_id)
        target_module_id = str(module.manifest.module_id if module is not None else module_id or "").strip()
        trace = KernelExecutionTrace(
            request_id=str(request.task_id or "").strip() or f"req-{int(time.time() * 1000)}",
            session_id=str(request.context.get("session_id") or "").strip(),
            module_id=target_module_id,
            selected_roles=list(request.context.get("selected_roles") or []),
            execution_policy=str(request.context.get("execution_policy") or ""),
            runtime_profile=str(request.context.get("runtime_profile") or ""),
        )
        self._trace_local.current = trace
        if module is None:
            trace.final_outcome = "failed"
            trace.error_summary = f"business module not found: {target_module_id or module_id or request.task_type}"
            trace.elapsed_ms = max(0, int((time.perf_counter() - started) * 1000))
            self.observe_and_record(trace)
            return TaskResponse(ok=False, task_id=request.task_id, error=trace.error_summary)

        injected = self.inject_tools_and_providers(module)
        trace.selected_tools = list(injected.get("selected_tools") or [])
        trace.selected_providers = list(injected.get("selected_providers") or [])
        runtime_context = RuntimeContext(
            request_id=trace.request_id,
            session_id=trace.session_id,
            module_id=module.manifest.module_id,
            execution_policy=trace.execution_policy,
            runtime_profile=trace.runtime_profile,
            selected_roles=list(trace.selected_roles),
            selected_tools=list(trace.selected_tools),
            selected_providers=list(trace.selected_providers),
            metadata={"required_system_modules": injected.get("required_system_modules") or []},
        )
        trace.add_event(TraceEvent(stage="resolve_module", module_id=module.manifest.module_id, detail=module.manifest.identity()))
        response = self.run_module(module, request, runtime_context)
        trace.selected_roles = list(runtime_context.selected_roles)
        trace.selected_tools = list(runtime_context.selected_tools)
        trace.selected_providers = list(runtime_context.selected_providers)
        if runtime_context.execution_policy:
            trace.execution_policy = runtime_context.execution_policy
        if runtime_context.runtime_profile:
            trace.runtime_profile = runtime_context.runtime_profile
        trace.health_state = runtime_context.health_state
        for event in list(runtime_context.metadata.get("trace_events") or []):
            if not isinstance(event, dict):
                continue
            trace.add_event(
                TraceEvent(
                    stage=str(event.get("stage") or "module_event"),
                    detail=str(event.get("detail") or ""),
                    status=str(event.get("status") or "ok"),
                    elapsed_ms=max(0, int(event.get("elapsed_ms") or 0)),
                    module_id=module.manifest.module_id,
                    payload=dict(event.get("payload") or {}),
                )
            )
        trace.final_outcome = "ok" if response.ok else "failed"
        trace.error_summary = str(response.error or "")
        trace.elapsed_ms = max(0, int((time.perf_counter() - started) * 1000))
        trace.add_event(TraceEvent(stage="module_complete", module_id=module.manifest.module_id, status="ok" if response.ok else "error", elapsed_ms=trace.elapsed_ms, detail=response.error or "module completed"))
        self.observe_and_record(trace)
        self._trace_local.current = None
        return response

    def invoke(self, module_id: str, request: TaskRequest) -> TaskResponse:
        return self.dispatch(request, module_id=module_id)

    def list_business_modules(self) -> list[BaseBusinessModule]:
        return [m for m in self.registry.list_modules(kind="business") if isinstance(m, BaseBusinessModule)]

    def hot_swap_module(self, module: BaseModule) -> dict[str, object]:
        module_id = str(module.manifest.module_id or "").strip()
        if not module_id:
            return {"ok": False, "error": "module_id is required"}

        previous = self.registry.get_module(module_id)
        if previous is not None and not bool(previous.manifest.hot_swappable):
            return {"ok": False, "error": f"module not hot swappable: {module_id}"}

        self.compatibility.assert_manifest_compatible(module.manifest)
        if self._initialized:
            self.lifecycle.init_module(module, kernel_context=self.context)
            report = module.health_check()
            if report.status == "unhealthy":
                return {"ok": False, "error": f"health check failed for {module.manifest.identity()}"}

        self.registry.register_module(module)
        self.registry.mark_module_state(module_id, lifecycle="ready")
        if previous is not None and previous is not module:
            try:
                previous.shutdown()
            except Exception:
                pass

        self.event_bus.publish(
            "module_swapped",
            {
                "module_id": module_id,
                "version": module.manifest.version,
                "previous_version": previous.manifest.version if previous else "",
            },
        )
        return {
            "ok": True,
            "module_id": module_id,
            "active_version": module.manifest.version,
            "previous_version": previous.manifest.version if previous else "",
        }

    def rollback_module(self, module_id: str) -> dict[str, object]:
        key = str(module_id or "").strip()
        if not key:
            return {"ok": False, "error": "module_id is required"}
        current = self.registry.get_module(key)
        rollback = self.rollback_manager.rollback_module(self.registry, key)
        if not rollback.get("ok"):
            return rollback
        previous = self.registry.get_module(key)
        if self._initialized and previous is not None:
            try:
                self.lifecycle.init_module(previous, kernel_context=self.context)
                report = previous.health_check()
                if report.status == "unhealthy":
                    raise RuntimeError("rollback health check failed")
            except Exception as exc:
                if current is not None:
                    self.registry.register_module(current)
                return {"ok": False, "error": f"rollback init failed: {exc}"}
        if current is not None and current is not previous:
            try:
                current.shutdown()
            except Exception:
                pass
        self.event_bus.publish(
            "module_rolled_back",
            {
                "module_id": key,
                "active_version": previous.manifest.version if previous else "",
                "from_version": current.manifest.version if current else "",
            },
        )
        return {
            "ok": True,
            "module_id": key,
            "active_version": previous.manifest.version if previous else "",
            "from_version": current.manifest.version if current else "",
        }

    def hot_swap_provider(self, provider: BaseToolProvider) -> dict[str, object]:
        provider_id = str(provider.provider_id or "").strip()
        if not provider_id:
            return {"ok": False, "error": "provider_id is required"}
        previous = self.registry.get_provider(provider_id)
        self.registry.register_provider(provider)
        try:
            report = provider.health_check()
        except Exception as exc:
            if previous is not None:
                self.registry.rollback_provider(provider_id)
            return {"ok": False, "error": f"provider health check failed: {exc}"}
        if report.status == "unhealthy":
            if previous is not None:
                self.registry.rollback_provider(provider_id)
            return {"ok": False, "error": f"provider unhealthy: {provider_id}"}
        self.registry.providers.record_success(provider_id)
        self.event_bus.publish("provider_swapped", {"provider_id": provider_id})
        return {"ok": True, "provider_id": provider_id}

    def rollback_provider(self, provider_id: str) -> dict[str, object]:
        key = str(provider_id or "").strip()
        if not key:
            return {"ok": False, "error": "provider_id is required"}
        rollback = self.rollback_manager.rollback_provider(self.registry, key)
        if rollback.get("ok"):
            self.event_bus.publish("provider_rolled_back", {"provider_id": key})
        return rollback

    def health_snapshot(self) -> dict[str, object]:
        payload = self.health_manager.collect(self.registry)
        payload["kernel_version"] = self.kernel_version
        payload["registry"] = self.registry.to_dict()
        payload["initialized"] = self._initialized
        payload["recent_traces"] = list(self._recent_traces[-5:])
        return payload

    def _capture_event(self, event: dict[str, Any]) -> None:
        trace = getattr(self._trace_local, "current", None)
        if not isinstance(trace, KernelExecutionTrace):
            return
        payload = dict(event)
        name = str(payload.pop("event", "") or "")
        detail = ""
        if name == "provider_failed":
            detail = str(payload.get("error") or "provider failed")
            trace.degraded_events.append(detail)
        elif name == "tool_fallback":
            detail = f"fallback -> {payload.get('provider_id') or ''}"
            trace.fallback_events.append(detail)
        elif name == "provider_circuit_open":
            detail = f"circuit open -> {payload.get('provider_id') or ''}"
            trace.degraded_events.append(detail)
        else:
            detail = str(payload.get("tool") or payload.get("provider_id") or payload.get("module_id") or name)
        trace.add_event(
            TraceEvent(
                stage=name,
                detail=detail,
                module_id=str(payload.get("module_id") or trace.module_id),
                tool_id=str(payload.get("tool") or ""),
                provider_id=str(payload.get("provider_id") or ""),
                payload=payload,
            )
        )
