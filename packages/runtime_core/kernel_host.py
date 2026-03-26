from __future__ import annotations

__doc__ = """Compatibility host for the legacy capability-runtime stack.

The formal Agent OS entrypoint is `app/kernel/host.py`. This host stays
in place because health/debug views and the current OfficeAgent
compatibility runtime still depend on capability-runtime surfaces during
migration.
"""

from typing import Any

from packages.agent_core import AgentCapabilityRuntime, build_agent_capability_runtime
from packages.runtime_core.blackboard import Blackboard


class KernelHost:
    def __init__(
        self,
        config: Any,
        *,
        kernel_runtime: Any | None = None,
        capability_runtime: AgentCapabilityRuntime | None = None,
    ) -> None:
        self.config = config
        if kernel_runtime is None:
            from app.core.bootstrap import build_kernel_runtime

            kernel_runtime = build_kernel_runtime(config)
        self.kernel_runtime = kernel_runtime
        self.capability_runtime = capability_runtime or build_agent_capability_runtime(config, config.capability_modules)
        self.agent_modules = tuple(self.capability_runtime.agent_modules)
        self.tool_modules = tuple(self.capability_runtime.tool_modules)
        self.output_modules = tuple(self.capability_runtime.output_modules)
        self.memory_modules = tuple(self.capability_runtime.memory_modules)
        self.primary_agent_module = self.capability_runtime.primary_agent_module
        self.primary_tool_module = self.capability_runtime.primary_tool_module
        self.primary_output_module = self.capability_runtime.primary_output_module
        self.primary_memory_module = self.capability_runtime.primary_memory_module
        if self.primary_agent_module is None:
            raise RuntimeError("No AgentModule is available in capability runtime")
        if self.primary_tool_module is None:
            raise RuntimeError("No ToolModule is available in capability runtime")
        self.tools = self.capability_runtime.tools
        self._last_blackboard: Blackboard | None = None
        builder = self.primary_agent_module.build_runtime
        if builder is None:
            raise RuntimeError(f"AgentModule {self.primary_agent_module.module_id} does not expose build_runtime")
        self._primary_agent = builder(
            config=config,
            kernel_runtime=self.kernel_runtime,
            capability_runtime=self.capability_runtime,
            tool_executor=self.tools,
            host=self,
        )

    def __getattr__(self, name: str) -> Any:
        return getattr(self._primary_agent, name)

    @property
    def primary_agent(self) -> Any:
        return self._primary_agent

    def create_blackboard(
        self,
        *,
        session_id: str | None,
        user_message: str,
        attachment_metas: list[dict[str, Any]] | None,
    ) -> Blackboard:
        return Blackboard.create(
            session_id=session_id,
            user_message=user_message,
            attachment_ids=[str((item or {}).get("id") or "").strip() for item in (attachment_metas or []) if str((item or {}).get("id") or "").strip()],
            selected_agent_module_id=self.primary_agent_module.module_id,
            selected_tool_module_id=self.primary_tool_module.module_id,
            selected_output_module_id=self.primary_output_module.module_id if self.primary_output_module else "",
            selected_memory_module_id=self.primary_memory_module.module_id if self.primary_memory_module else "",
            selected_capability_modules=[item.module_id for item in self.capability_runtime.bundles],
        )

    def run_chat(
        self,
        history_turns: list[dict[str, Any]],
        summary: str,
        user_message: str,
        attachment_metas: list[dict[str, Any]],
        settings: Any,
        session_id: str | None = None,
        route_state: dict[str, Any] | None = None,
        progress_cb: Any | None = None,
    ):
        blackboard = self.create_blackboard(
            session_id=session_id,
            user_message=user_message,
            attachment_metas=attachment_metas,
        )
        self._last_blackboard = blackboard
        blackboard.start()
        try:
            result = self._primary_agent.run_chat(
                history_turns,
                summary,
                user_message,
                attachment_metas,
                settings,
                session_id=session_id,
                route_state=route_state,
                progress_cb=progress_cb,
                blackboard=blackboard,
            )
            blackboard.complete(
                effective_model=str(result[13] if len(result) > 13 else ""),
                route_state=result[14] if len(result) > 14 and isinstance(result[14], dict) else {},
                execution_plan=result[3] if len(result) > 3 and isinstance(result[3], list) else [],
                execution_trace=result[4] if len(result) > 4 and isinstance(result[4], list) else [],
                tool_events=result[1] if len(result) > 1 and isinstance(result[1], list) else [],
                answer_bundle=result[11] if len(result) > 11 and isinstance(result[11], dict) else {},
            )
            return result
        except Exception as exc:
            blackboard.fail(str(exc))
            raise

    def _debug_kernel_host_snapshot(self) -> dict[str, Any]:
        return {
            "agent_modules": [
                {
                    "module_id": item.module_id,
                    "title": item.title,
                    "description": item.description,
                    "roles": list(item.roles),
                    "profiles": list(item.profiles),
                }
                for item in self.agent_modules
            ],
            "primary_agent_module": {
                "module_id": self.primary_agent_module.module_id,
                "title": self.primary_agent_module.title,
                "description": self.primary_agent_module.description,
                "roles": list(self.primary_agent_module.roles),
                "profiles": list(self.primary_agent_module.profiles),
            }
            if self.primary_agent_module
            else {},
            "tool_modules": [
                {
                    "module_id": item.module_id,
                    "title": item.title,
                    "description": item.description,
                    "tool_names": list(item.tool_names),
                    "group": str(item.metadata.get("group") or ""),
                }
                for item in self.tool_modules
            ],
            "primary_tool_module": {
                "module_id": self.primary_tool_module.module_id,
                "title": self.primary_tool_module.title,
                "description": self.primary_tool_module.description,
                "tool_names": list(self.primary_tool_module.tool_names),
            }
            if self.primary_tool_module
            else {},
            "output_modules": [
                {
                    "module_id": item.module_id,
                    "title": item.title,
                    "description": item.description,
                    "output_kinds": list(item.output_kinds),
                }
                for item in self.output_modules
            ],
            "memory_modules": [
                {
                    "module_id": item.module_id,
                    "title": item.title,
                    "description": item.description,
                    "signal_kinds": list(item.signal_kinds),
                }
                for item in self.memory_modules
            ],
            "primary_output_module": {
                "module_id": self.primary_output_module.module_id,
                "title": self.primary_output_module.title,
                "description": self.primary_output_module.description,
                "output_kinds": list(self.primary_output_module.output_kinds),
            }
            if self.primary_output_module
            else {},
            "primary_memory_module": {
                "module_id": self.primary_memory_module.module_id,
                "title": self.primary_memory_module.title,
                "description": self.primary_memory_module.description,
                "signal_kinds": list(self.primary_memory_module.signal_kinds),
            }
            if self.primary_memory_module
            else {},
            "capability_modules": list(self.capability_runtime.metadata.get("module_paths") or []),
            "loaded_capability_bundles": [item.get("module_id") for item in self.capability_runtime.metadata.get("modules") or []],
            "tool_dispatch_modules": list(self.capability_runtime.metadata.get("tool_dispatch_modules") or []),
            "role_sources": dict(self.capability_runtime.metadata.get("role_sources") or {}),
            "blackboard": self._last_blackboard.snapshot() if self._last_blackboard else {},
        }
