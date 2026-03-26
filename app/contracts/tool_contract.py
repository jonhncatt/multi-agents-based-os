from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ToolContract:
    tool_id: str
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    timeout: float = 0.0
    retry_policy: dict[str, Any] = field(default_factory=dict)
    permission_scope: str = ""
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_id": self.tool_id,
            "input_schema": dict(self.input_schema),
            "output_schema": dict(self.output_schema),
            "timeout": float(self.timeout),
            "retry_policy": dict(self.retry_policy),
            "permission_scope": self.permission_scope,
            "description": self.description,
        }
