from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


ModuleKind = Literal["system", "business"]
CompatibilityLevel = Literal["native", "shim", "deprecated"]


@dataclass(slots=True)
class ModuleManifest:
    module_id: str
    module_kind: ModuleKind
    version: str
    description: str
    capabilities: list[str] = field(default_factory=list)
    required_tools: list[str] = field(default_factory=list)
    optional_tools: list[str] = field(default_factory=list)
    required_system_modules: list[str] = field(default_factory=list)
    min_kernel_version: str = "1.0.0"
    hot_swappable: bool = True
    entrypoint: str = ""
    owner: str = ""
    healthcheck: str = "health_check"
    rollback_strategy: str = "registry_rollback"
    compatibility_level: CompatibilityLevel = "native"

    @property
    def module_type(self) -> ModuleKind:
        return self.module_kind

    def identity(self) -> str:
        return f"{self.module_id}@{self.version}"

    def to_dict(self) -> dict[str, object]:
        return {
            "module_id": self.module_id,
            "module_kind": self.module_kind,
            "module_type": self.module_kind,
            "version": self.version,
            "description": self.description,
            "capabilities": list(self.capabilities),
            "required_tools": list(self.required_tools),
            "optional_tools": list(self.optional_tools),
            "required_system_modules": list(self.required_system_modules),
            "min_kernel_version": self.min_kernel_version,
            "hot_swappable": bool(self.hot_swappable),
            "entrypoint": self.entrypoint,
            "owner": self.owner,
            "healthcheck": self.healthcheck,
            "rollback_strategy": self.rollback_strategy,
            "compatibility_level": self.compatibility_level,
        }
