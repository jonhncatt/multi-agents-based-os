from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ProviderContract:
    provider_id: str
    supported_tools: list[str] = field(default_factory=list)
    timeout_policy: dict[str, Any] = field(default_factory=dict)
    degraded_behavior: str = ""
    healthcheck: str = "health_check"

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "supported_tools": list(self.supported_tools),
            "timeout_policy": dict(self.timeout_policy),
            "degraded_behavior": self.degraded_behavior,
            "healthcheck": self.healthcheck,
        }
