from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(slots=True)
class TraceEvent:
    stage: str
    detail: str = ""
    status: str = "ok"
    elapsed_ms: int = 0
    module_id: str = ""
    tool_id: str = ""
    provider_id: str = ""
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self, *, verbose: bool = False) -> dict[str, Any]:
        base = {
            "stage": self.stage,
            "detail": self.detail,
            "status": self.status,
            "elapsed_ms": self.elapsed_ms,
            "module_id": self.module_id,
            "tool_id": self.tool_id,
            "provider_id": self.provider_id,
        }
        if verbose:
            base["payload"] = dict(self.payload)
        return base


@dataclass(slots=True)
class KernelExecutionTrace:
    request_id: str
    session_id: str = ""
    module_id: str = ""
    selected_roles: list[str] = field(default_factory=list)
    selected_tools: list[str] = field(default_factory=list)
    selected_providers: list[str] = field(default_factory=list)
    execution_policy: str = ""
    runtime_profile: str = ""
    health_state: str = "ready"
    degraded_events: list[str] = field(default_factory=list)
    fallback_events: list[str] = field(default_factory=list)
    final_outcome: str = "pending"
    elapsed_ms: int = 0
    error_summary: str = ""
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    events: list[TraceEvent] = field(default_factory=list)

    def add_event(self, event: TraceEvent) -> None:
        self.events.append(event)

    def to_dict(self, *, verbose: bool = False) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "session_id": self.session_id,
            "module_id": self.module_id,
            "selected_roles": list(self.selected_roles),
            "selected_tools": list(self.selected_tools),
            "selected_providers": list(self.selected_providers),
            "execution_policy": self.execution_policy,
            "runtime_profile": self.runtime_profile,
            "health_state": self.health_state,
            "degraded_events": list(self.degraded_events),
            "fallback_events": list(self.fallback_events),
            "final_outcome": self.final_outcome,
            "elapsed_ms": self.elapsed_ms,
            "error_summary": self.error_summary,
            "started_at": self.started_at,
            "events": [item.to_dict(verbose=verbose) for item in self.events],
        }
