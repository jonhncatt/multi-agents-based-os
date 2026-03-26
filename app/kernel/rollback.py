from __future__ import annotations

from app.kernel.registry import ModuleRegistry


class RollbackManager:
    def rollback_module(self, registry: ModuleRegistry, module_id: str) -> dict[str, object]:
        previous = registry.rollback_module(module_id)
        if previous is None:
            return {"ok": False, "error": f"no rollback candidate for module: {module_id}"}
        registry.mark_module_state(module_id, lifecycle="rollback")
        return {
            "ok": True,
            "module_id": module_id,
            "active_version": previous.manifest.version,
        }

    def rollback_provider(self, registry: ModuleRegistry, provider_id: str) -> dict[str, object]:
        previous = registry.rollback_provider(provider_id)
        if previous is None:
            return {"ok": False, "error": f"no rollback candidate for provider: {provider_id}"}
        registry.providers.mark_status(provider_id, "ready")
        return {"ok": True, "provider_id": provider_id}
