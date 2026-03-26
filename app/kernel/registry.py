from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.contracts import BaseBusinessModule, BaseModule, BaseToolProvider, ToolContract, provider_contract_from_instance


@dataclass(slots=True)
class ModuleRuntimeState:
    module_id: str
    lifecycle: str = "init"
    health_status: str = "unknown"
    last_error: str = ""
    compatibility_level: str = "native"

    def to_dict(self) -> dict[str, Any]:
        return {
            "module_id": self.module_id,
            "lifecycle": self.lifecycle,
            "health_status": self.health_status,
            "last_error": self.last_error,
            "compatibility_level": self.compatibility_level,
        }


@dataclass(slots=True)
class ProviderRuntimeState:
    provider_id: str
    status: str = "ready"
    failure_count: int = 0
    last_error: str = ""
    circuit_open: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "status": self.status,
            "failure_count": self.failure_count,
            "last_error": self.last_error,
            "circuit_open": self.circuit_open,
        }


@dataclass(slots=True)
class ToolRoute:
    tool_id: str
    contract: ToolContract | None = None
    primary_provider: str = ""
    fallback_providers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_id": self.tool_id,
            "contract": self.contract.to_dict() if self.contract else {},
            "primary_provider": self.primary_provider,
            "fallback_providers": list(self.fallback_providers),
        }


@dataclass(slots=True)
class RegistrySnapshot:
    system_modules: list[str]
    business_modules: list[str]
    providers: list[str]
    tool_map: dict[str, str]
    active_module_versions: dict[str, str]
    module_states: dict[str, dict[str, Any]]
    provider_states: dict[str, dict[str, Any]]
    tool_contracts: dict[str, dict[str, Any]]


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, BaseToolProvider] = {}
        self._provider_history: dict[str, list[BaseToolProvider]] = {}
        self._states: dict[str, ProviderRuntimeState] = {}
        self._contracts: dict[str, dict[str, Any]] = {}

    def register(self, provider: BaseToolProvider) -> None:
        provider_id = str(provider.provider_id or "").strip()
        if not provider_id:
            raise ValueError("provider_id is required")
        existing = self._providers.get(provider_id)
        if existing is not None:
            self._provider_history.setdefault(provider_id, []).append(existing)
        self._providers[provider_id] = provider
        self._states.setdefault(provider_id, ProviderRuntimeState(provider_id=provider_id))
        self._contracts[provider_id] = provider_contract_from_instance(provider).to_dict()

    def rollback(self, provider_id: str) -> BaseToolProvider | None:
        key = str(provider_id or "").strip()
        history = self._provider_history.get(key) or []
        if not history:
            return None
        previous = history.pop()
        self._providers[key] = previous
        self._contracts[key] = provider_contract_from_instance(previous).to_dict()
        self._states.setdefault(key, ProviderRuntimeState(provider_id=key))
        return previous

    def get(self, provider_id: str) -> BaseToolProvider | None:
        return self._providers.get(str(provider_id or "").strip())

    def list(self) -> list[BaseToolProvider]:
        return list(self._providers.values())

    def state(self, provider_id: str) -> ProviderRuntimeState:
        key = str(provider_id or "").strip()
        return self._states.setdefault(key, ProviderRuntimeState(provider_id=key))

    def mark_status(self, provider_id: str, status: str, *, error: str = "") -> None:
        state = self.state(provider_id)
        state.status = status
        if error:
            state.last_error = error
        if status != "degraded":
            state.circuit_open = False

    def record_failure(self, provider_id: str, error: str) -> ProviderRuntimeState:
        state = self.state(provider_id)
        state.failure_count += 1
        state.last_error = str(error or "")
        if state.failure_count >= 3:
            state.status = "degraded"
            state.circuit_open = True
        return state

    def record_success(self, provider_id: str) -> ProviderRuntimeState:
        state = self.state(provider_id)
        state.failure_count = 0
        state.last_error = ""
        if state.status != "disabled":
            state.status = "ready"
            state.circuit_open = False
        return state

    def snapshot(self) -> dict[str, dict[str, Any]]:
        return {key: value.to_dict() for key, value in sorted(self._states.items())}

    def contracts(self) -> dict[str, dict[str, Any]]:
        return dict(sorted(self._contracts.items()))


class ToolRegistry:
    def __init__(self) -> None:
        self._routes: dict[str, ToolRoute] = {}

    def register_contract(
        self,
        contract: ToolContract,
        *,
        primary_provider: str = "",
        fallback_providers: list[str] | None = None,
    ) -> None:
        tool_id = str(contract.tool_id or "").strip()
        if not tool_id:
            raise ValueError("tool_id is required")
        route = self._routes.get(tool_id) or ToolRoute(tool_id=tool_id)
        route.contract = contract
        if primary_provider:
            route.primary_provider = str(primary_provider).strip()
        if fallback_providers is not None:
            route.fallback_providers = [str(item or "").strip() for item in fallback_providers if str(item or "").strip()]
        self._routes[tool_id] = route

    def bind_provider(self, tool_id: str, provider_id: str, *, as_fallback: bool = False) -> None:
        key = str(tool_id or "").strip()
        provider_key = str(provider_id or "").strip()
        if not key or not provider_key:
            return
        route = self._routes.get(key) or ToolRoute(tool_id=key)
        if as_fallback:
            if provider_key not in route.fallback_providers:
                route.fallback_providers.append(provider_key)
        elif not route.primary_provider:
            route.primary_provider = provider_key
        elif route.primary_provider != provider_key and provider_key not in route.fallback_providers:
            route.fallback_providers.append(provider_key)
        self._routes[key] = route

    def route_for(self, tool_id: str) -> ToolRoute | None:
        return self._routes.get(str(tool_id or "").strip())

    def contract_for(self, tool_id: str) -> ToolContract | None:
        route = self.route_for(tool_id)
        return route.contract if route else None

    def providers_for(self, tool_id: str, provider_registry: ProviderRegistry) -> list[str]:
        route = self.route_for(tool_id)
        if route is None:
            return []
        ordered = [route.primary_provider, *route.fallback_providers]
        out: list[str] = []
        for provider_id in ordered:
            provider_key = str(provider_id or "").strip()
            if not provider_key:
                continue
            state = provider_registry.state(provider_key)
            if state.status == "disabled" or state.circuit_open:
                continue
            if provider_key not in out:
                out.append(provider_key)
        return out

    def fallback_provider_ids(self, tool_id: str) -> list[str]:
        route = self.route_for(tool_id)
        return list(route.fallback_providers) if route else []

    def snapshot(self) -> dict[str, dict[str, Any]]:
        return {key: route.to_dict() for key, route in sorted(self._routes.items())}


class ModuleRegistry:
    def __init__(self) -> None:
        self._system_modules: dict[str, BaseModule] = {}
        self._business_modules: dict[str, BaseBusinessModule] = {}
        self._module_history: dict[str, list[BaseModule]] = {}
        self._module_versions: dict[str, str] = {}
        self._module_states: dict[str, ModuleRuntimeState] = {}
        self.providers = ProviderRegistry()
        self.tools = ToolRegistry()

    def register_module(self, module: BaseModule) -> None:
        module_id = str(module.manifest.module_id or "").strip()
        if not module_id:
            raise ValueError("module_id is required")
        existing = self.get_module(module_id)
        if existing is not None:
            self._module_history.setdefault(module_id, []).append(existing)
        if module.manifest.module_kind == "business":
            self._business_modules[module_id] = module  # type: ignore[assignment]
            self._system_modules.pop(module_id, None)
        else:
            self._system_modules[module_id] = module
            self._business_modules.pop(module_id, None)
        self._module_versions[module_id] = str(module.manifest.version or "")
        self._module_states[module_id] = ModuleRuntimeState(
            module_id=module_id,
            lifecycle="init",
            compatibility_level=str(getattr(module.manifest, "compatibility_level", "native") or "native"),
        )

    def rollback_module(self, module_id: str) -> BaseModule | None:
        key = str(module_id or "").strip()
        history = self._module_history.get(key) or []
        if not history:
            return None
        previous = history.pop()
        if previous.manifest.module_kind == "business":
            self._business_modules[key] = previous  # type: ignore[assignment]
            self._system_modules.pop(key, None)
        else:
            self._system_modules[key] = previous
            self._business_modules.pop(key, None)
        self._module_versions[key] = str(previous.manifest.version or "")
        self.mark_module_state(key, lifecycle="rollback")
        return previous

    def active_module_version(self, module_id: str) -> str:
        return str(self._module_versions.get(str(module_id or "").strip()) or "")

    def mark_module_state(self, module_id: str, *, lifecycle: str | None = None, error: str = "") -> None:
        key = str(module_id or "").strip()
        state = self._module_states.setdefault(key, ModuleRuntimeState(module_id=key))
        if lifecycle:
            state.lifecycle = lifecycle
        if error:
            state.last_error = error

    def mark_module_health(self, module_id: str, status: str, *, summary: str = "") -> None:
        key = str(module_id or "").strip()
        state = self._module_states.setdefault(key, ModuleRuntimeState(module_id=key))
        state.health_status = status
        if summary:
            state.last_error = summary if status == "unhealthy" else state.last_error

    def module_state(self, module_id: str) -> ModuleRuntimeState:
        key = str(module_id or "").strip()
        return self._module_states.setdefault(key, ModuleRuntimeState(module_id=key))

    def register_provider(self, provider: BaseToolProvider) -> None:
        self.providers.register(provider)
        provider_id = str(provider.provider_id or "").strip()
        for tool_name in list(getattr(provider, "supported_tools", []) or []):
            self.tools.bind_provider(str(tool_name or "").strip(), provider_id)

    def rollback_provider(self, provider_id: str) -> BaseToolProvider | None:
        return self.providers.rollback(provider_id)

    def register_tool_contract(
        self,
        contract: ToolContract,
        *,
        primary_provider: str = "",
        fallback_providers: list[str] | None = None,
    ) -> None:
        self.tools.register_contract(contract, primary_provider=primary_provider, fallback_providers=fallback_providers)

    def bind_tool_provider(self, tool_id: str, provider_id: str, *, as_fallback: bool = False) -> None:
        self.tools.bind_provider(tool_id, provider_id, as_fallback=as_fallback)

    def provider_for_tool(self, tool_name: str) -> BaseToolProvider | None:
        provider_ids = self.tools.providers_for(tool_name, self.providers)
        if not provider_ids:
            return None
        return self.providers.get(provider_ids[0])

    def providers_for_tool(self, tool_name: str) -> list[BaseToolProvider]:
        return [provider for provider_id in self.tools.providers_for(tool_name, self.providers) if (provider := self.providers.get(provider_id)) is not None]

    def get_tool_contract(self, tool_name: str) -> ToolContract | None:
        return self.tools.contract_for(tool_name)

    def get_provider(self, provider_id: str) -> BaseToolProvider | None:
        return self.providers.get(provider_id)

    def get_module(self, module_id: str) -> BaseModule | None:
        key = str(module_id or "").strip()
        if key in self._business_modules:
            return self._business_modules[key]
        return self._system_modules.get(key)

    def get_business_module(self, module_id: str) -> BaseBusinessModule | None:
        return self._business_modules.get(str(module_id or "").strip())

    def list_modules(self, *, kind: str | None = None) -> list[BaseModule]:
        if kind == "business":
            return list(self._business_modules.values())
        if kind == "system":
            return list(self._system_modules.values())
        return [*self._system_modules.values(), *self._business_modules.values()]

    def list_providers(self) -> list[BaseToolProvider]:
        return self.providers.list()

    def state_counts(self) -> dict[str, int]:
        module_counts: dict[str, int] = {}
        for state in self._module_states.values():
            module_counts[state.lifecycle] = module_counts.get(state.lifecycle, 0) + 1
        provider_counts: dict[str, int] = {}
        for state in self.providers.snapshot().values():
            status = str(state.get("status") or "unknown")
            provider_counts[status] = provider_counts.get(status, 0) + 1
        return {"modules": module_counts, "providers": provider_counts}

    def snapshot(self) -> RegistrySnapshot:
        return RegistrySnapshot(
            system_modules=sorted(self._system_modules.keys()),
            business_modules=sorted(self._business_modules.keys()),
            providers=sorted(str(getattr(item, "provider_id", "") or "") for item in self.providers.list()),
            tool_map={
                tool_id: route.primary_provider
                for tool_id, route in sorted(self.tools._routes.items())
                if route.primary_provider
            },
            active_module_versions=dict(sorted(self._module_versions.items())),
            module_states={key: value.to_dict() for key, value in sorted(self._module_states.items())},
            provider_states=self.providers.snapshot(),
            tool_contracts=self.tools.snapshot(),
        )

    def to_dict(self) -> dict[str, Any]:
        snap = self.snapshot()
        return {
            "system_modules": snap.system_modules,
            "business_modules": snap.business_modules,
            "providers": snap.providers,
            "tool_map": dict(snap.tool_map),
            "active_module_versions": dict(snap.active_module_versions),
            "module_history_depth": {key: len(items) for key, items in sorted(self._module_history.items()) if items},
            "provider_history_depth": {
                key: len(items)
                for key, items in sorted(self.providers._provider_history.items())
                if items
            },
            "module_states": dict(snap.module_states),
            "provider_states": dict(snap.provider_states),
            "tool_contracts": dict(snap.tool_contracts),
        }
