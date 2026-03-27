from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ExecutionState:
    task_type: str = "standard"
    complexity: str = "medium"
    tool_mode: str = "auto"  # off | auto | on | forced
    tool_latch: bool = False
    attempts: int = 0
    max_attempts: int = 24
    status: str = "initialized"
    transitions: list[str] = field(default_factory=list)


__all__ = ["ExecutionState"]
