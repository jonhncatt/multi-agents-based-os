from __future__ import annotations

from app.contracts.health import HealthReport
from app.kernel.registry import ModuleRegistry


class HealthManager:
    def collect(self, registry: ModuleRegistry) -> dict[str, object]:
        module_reports: list[dict[str, object]] = []
        provider_reports: list[dict[str, object]] = []

        for module in registry.list_modules():
            report = self._module_report(module)
            registry.mark_module_health(module.manifest.module_id, report.status, summary=report.summary)
            module_reports.append(report.to_dict())

        for provider in registry.list_providers():
            report = self._provider_report(provider)
            registry.providers.mark_status(provider.provider_id, "degraded" if report.status == "degraded" else ("disabled" if report.status == "unhealthy" else "ready"), error=report.summary)
            provider_reports.append(report.to_dict())

        combined = [*module_reports, *provider_reports]
        all_ok = all(bool(item.get("ok")) for item in combined) if combined else True
        return {
            "ok": all_ok,
            "modules": module_reports,
            "providers": provider_reports,
            "state_counts": registry.state_counts(),
        }

    def startup_check(self, registry: ModuleRegistry) -> dict[str, object]:
        return self.collect(registry)

    def _module_report(self, module: object) -> HealthReport:
        try:
            report = module.health_check()  # type: ignore[attr-defined]
        except Exception as exc:
            report = HealthReport(
                component_id=str(getattr(getattr(module, "manifest", None), "module_id", "") or "unknown_module"),
                status="unhealthy",
                summary=f"health_check exception: {exc}",
            )
        return report

    def _provider_report(self, provider: object) -> HealthReport:
        try:
            report = provider.health_check()  # type: ignore[attr-defined]
        except Exception as exc:
            report = HealthReport(
                component_id=str(getattr(provider, "provider_id", "") or "unknown_provider"),
                status="unhealthy",
                summary=f"health_check exception: {exc}",
            )
        return report


HealthMonitor = HealthManager
