from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class RuntimeContext:
    request_id: str
    session_id: str = ""
    module_id: str = ""
    execution_policy: str = ""
    runtime_profile: str = ""
    selected_roles: list[str] = field(default_factory=list)
    selected_tools: list[str] = field(default_factory=list)
    selected_providers: list[str] = field(default_factory=list)
    health_state: str = "ready"
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_trace_event(
        self,
        *,
        stage: str,
        detail: str,
        status: str = "ok",
        elapsed_ms: int = 0,
        payload: dict[str, Any] | None = None,
    ) -> None:
        events = self.metadata.get("trace_events")
        if not isinstance(events, list):
            events = []
            self.metadata["trace_events"] = events
        events.append(
            {
                "stage": str(stage or "").strip() or "module_event",
                "detail": str(detail or "").strip(),
                "status": str(status or "").strip() or "ok",
                "elapsed_ms": max(0, int(elapsed_ms)),
                "payload": dict(payload or {}),
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "session_id": self.session_id,
            "module_id": self.module_id,
            "execution_policy": self.execution_policy,
            "runtime_profile": self.runtime_profile,
            "selected_roles": list(self.selected_roles),
            "selected_tools": list(self.selected_tools),
            "selected_providers": list(self.selected_providers),
            "health_state": self.health_state,
            "metadata": dict(self.metadata),
        }
