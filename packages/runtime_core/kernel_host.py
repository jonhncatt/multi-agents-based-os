from __future__ import annotations

__doc__ = """Compatibility host for the legacy capability-runtime stack.

The formal Agent OS entrypoint is `app/kernel/host.py`. This host stays
in place because health/debug views and the current OfficeAgent
compatibility runtime still depend on capability-runtime surfaces during
migration.
"""

import logging
from typing import Any

from packages.agent_core import AgentCapabilityRuntime, build_agent_capability_runtime
from packages.runtime_core.blackboard import Blackboard
from packages.runtime_core.legacy_host_support import (
    build_primary_agent,
    compact_primary_agent_session,
    create_blackboard,
    kernel_host_snapshot,
    read_kernel_host_getattr_metrics,
    record_kernel_host_getattr_access,
    run_primary_agent_chat_with_blackboard,
)

logger = logging.getLogger(__name__)


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
        self._primary_agent = build_primary_agent(
            config=config,
            kernel_runtime=self.kernel_runtime,
            capability_runtime=self.capability_runtime,
            tool_executor=self.tools,
            host=self,
        )

    def __getattr__(self, name: str) -> Any:
        value = getattr(self._primary_agent, name)
        if record_kernel_host_getattr_access(name):
            logger.warning("KernelHost __getattr__ fallback accessed compatibility attribute: %s", name)
        return value

    @property
    def primary_agent(self) -> Any:
        return self._primary_agent

    def compact_session(self, session: dict[str, Any], keep_last_turns: int) -> bool:
        return bool(compact_primary_agent_session(self._primary_agent, session, keep_last_turns))

    def role_lab_runtime_snapshot(self) -> dict[str, Any]:
        return dict(self._primary_agent._debug_role_lab_runtime_snapshot() or {})

    def tool_registry_snapshot(self) -> dict[str, Any]:
        return dict(self._primary_agent._debug_tool_registry_snapshot() or {})

    def route_request_by_rules(
        self,
        *,
        user_message: str,
        attachment_metas: list[dict[str, Any]],
        settings: Any,
        route_state: dict[str, Any] | None = None,
        inline_followup_context: bool = False,
    ) -> dict[str, Any]:
        return dict(
            self._primary_agent._route_request_by_rules(
                user_message=user_message,
                attachment_metas=attachment_metas,
                settings=settings,
                route_state=route_state,
                inline_followup_context=inline_followup_context,
            )
            or {}
        )

    def _route_request_by_rules(
        self,
        *,
        user_message: str,
        attachment_metas: list[dict[str, Any]],
        settings: Any,
        route_state: dict[str, Any] | None = None,
        inline_followup_context: bool = False,
    ) -> dict[str, Any]:
        return self.route_request_by_rules(
            user_message=user_message,
            attachment_metas=attachment_metas,
            settings=settings,
            route_state=route_state,
            inline_followup_context=inline_followup_context,
        )

    def build_session_route_state(self, route: dict[str, Any]) -> dict[str, Any]:
        return dict(self._primary_agent._build_session_route_state(route) or {})

    def _build_session_route_state(self, route: dict[str, Any]) -> dict[str, Any]:
        return self.build_session_route_state(route)

    def normalize_route_decision(
        self,
        *,
        route: dict[str, Any],
        fallback: dict[str, Any] | None = None,
        settings: Any | None = None,
    ) -> dict[str, Any]:
        return dict(
            self._primary_agent._normalize_route_decision_impl(
                route=route,
                fallback=fallback,
                settings=settings,
            )
            or {}
        )

    def _normalize_route_decision_impl(
        self,
        *,
        route: dict[str, Any],
        fallback: dict[str, Any] | None = None,
        settings: Any | None = None,
    ) -> dict[str, Any]:
        return self.normalize_route_decision(route=route, fallback=fallback, settings=settings)

    def _debug_kernel_module_snapshot(self) -> dict[str, Any]:
        return dict(self._primary_agent._debug_kernel_module_snapshot() or {})

    def _debug_tool_registry_snapshot(self) -> dict[str, Any]:
        return dict(self._primary_agent._debug_tool_registry_snapshot() or {})

    def _debug_role_contract_matrix(self) -> dict[str, Any]:
        return dict(self._primary_agent._debug_role_contract_matrix() or {})

    def _debug_capability_multi_module_snapshot(self) -> dict[str, Any]:
        return dict(self._primary_agent._debug_capability_multi_module_snapshot() or {})

    def _debug_route_runtime_override_attachment_context_requires_tooling(self) -> dict[str, Any]:
        return dict(self._primary_agent._debug_route_runtime_override_attachment_context_requires_tooling() or {})

    def _debug_route_runtime_override_force_tool_followup(self) -> dict[str, Any]:
        return dict(self._primary_agent._debug_route_runtime_override_force_tool_followup() or {})

    def _summarize_validation_context(self, tool_events: list[Any]) -> dict[str, Any]:
        return dict(self._primary_agent._summarize_validation_context(tool_events) or {})

    def _hook_before_route_finalize(
        self,
        *,
        route: dict[str, Any],
        router_raw: str,
        planner_user_message: str,
        attachment_issues: list[str],
        followup_has_attachments: bool,
        followup_attachment_requires_tools: bool,
        attachment_metas: list[dict[str, Any]],
        settings: Any,
    ) -> Any:
        return self._primary_agent._hook_before_route_finalize(
            route=route,
            router_raw=router_raw,
            planner_user_message=planner_user_message,
            attachment_issues=attachment_issues,
            followup_has_attachments=followup_has_attachments,
            followup_attachment_requires_tools=followup_attachment_requires_tools,
            attachment_metas=attachment_metas,
            settings=settings,
        )

    def _build_followup_topic_hint(self, *, user_message: str, history_turns: list[dict[str, Any]]) -> str:
        return str(self._primary_agent._build_followup_topic_hint(user_message=user_message, history_turns=history_turns) or "")

    def _should_force_initial_tool_execution(
        self,
        user_message: str,
        attachment_metas: list[dict[str, Any]],
    ) -> bool:
        return bool(self._primary_agent._should_force_initial_tool_execution(user_message, attachment_metas))

    def create_blackboard(
        self,
        *,
        session_id: str | None,
        user_message: str,
        attachment_metas: list[dict[str, Any]] | None,
    ) -> Blackboard:
        return create_blackboard(
            session_id=session_id,
            user_message=user_message,
            attachment_metas=attachment_metas,
            primary_agent_module=self.primary_agent_module,
            primary_tool_module=self.primary_tool_module,
            primary_output_module=self.primary_output_module,
            primary_memory_module=self.primary_memory_module,
            capability_runtime=self.capability_runtime,
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
        return run_primary_agent_chat_with_blackboard(
            primary_agent=self._primary_agent,
            blackboard=blackboard,
            history_turns=history_turns,
            summary=summary,
            user_message=user_message,
            attachment_metas=attachment_metas,
            settings=settings,
            session_id=session_id,
            route_state=route_state,
            progress_cb=progress_cb,
        )

    def _debug_kernel_host_snapshot(self) -> dict[str, Any]:
        return kernel_host_snapshot(
            agent_modules=self.agent_modules,
            primary_agent_module=self.primary_agent_module,
            tool_modules=self.tool_modules,
            primary_tool_module=self.primary_tool_module,
            output_modules=self.output_modules,
            primary_output_module=self.primary_output_module,
            memory_modules=self.memory_modules,
            primary_memory_module=self.primary_memory_module,
            capability_runtime=self.capability_runtime,
            blackboard=self._last_blackboard,
            getattr_metrics=read_kernel_host_getattr_metrics(),
        )
