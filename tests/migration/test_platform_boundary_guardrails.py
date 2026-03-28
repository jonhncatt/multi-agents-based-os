from __future__ import annotations

from scripts.check_platform_boundaries import _active_shim_import_violations, _legacy_host_object_access_violations
from scripts.collect_platform_metrics import _shim_metrics


def test_active_shim_dependency_allowlist_has_no_current_violations() -> None:
    assert _active_shim_import_violations() == []


def test_shim_metrics_include_active_dependency_counts() -> None:
    metrics = _shim_metrics()
    counts = metrics["active_shim_dependency_counts"]
    dependents = metrics["active_shim_dependents"]

    assert counts["app.agent"] == 1
    assert "app/evals.py" not in dependents["app.agent"]
    assert "app/business_modules/office_module/module.py" not in dependents["app.agent"]
    assert "app/core/bootstrap.py" not in dependents["app.agent"]
    assert "packages/office_modules/agent_module.py" in dependents["app.agent"]
    assert "packages.runtime_core.kernel_host" not in dependents
    assert "kernel_host_getattr" in metrics


def test_runtime_code_does_not_access_whole_legacy_host_outside_allowlist() -> None:
    assert _legacy_host_object_access_violations() == []
