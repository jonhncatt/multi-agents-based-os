from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


RoleKind = Literal["agent", "processor", "hybrid"]


@dataclass(slots=True)
class RoleSpec:
    role: str
    kind: RoleKind = "agent"
    llm_driven: bool = True
    description: str = ""
    tool_names: tuple[str, ...] = ()
    output_keys: tuple[str, ...] = ()


@dataclass(slots=True)
class RoleContext:
    role: str
    requested_model: str = ""
    user_message: str = ""
    effective_user_message: str = ""
    history_summary: str = ""
    attachment_metas: list[dict[str, Any]] = field(default_factory=list)
    tool_events: list[Any] = field(default_factory=list)
    planner_brief: dict[str, Any] = field(default_factory=dict)
    reviewer_brief: dict[str, Any] = field(default_factory=dict)
    conflict_brief: dict[str, Any] = field(default_factory=dict)
    route: dict[str, Any] = field(default_factory=dict)
    execution_trace: list[str] = field(default_factory=list)
    response_text: str = ""
    user_content: Any = None
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def primary_user_request(self) -> str:
        return self.effective_user_message.strip() or self.user_message.strip()


@dataclass(slots=True)
class RoleResult:
    spec: RoleSpec
    context: RoleContext
    payload: dict[str, Any] = field(default_factory=dict)
    raw_text: str = ""
    summary: str = ""
    usage: dict[str, int] = field(default_factory=dict)
    effective_model: str = ""
    notes: list[str] = field(default_factory=list)

