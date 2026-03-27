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
