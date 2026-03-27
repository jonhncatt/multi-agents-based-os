from __future__ import annotations

from scripts.check_platform_boundaries import _active_shim_import_violations
from scripts.collect_platform_metrics import _shim_metrics


def test_active_shim_dependency_allowlist_has_no_current_violations() -> None:
    assert _active_shim_import_violations() == []


def test_shim_metrics_include_active_dependency_counts() -> None:
    metrics = _shim_metrics()
    counts = metrics["active_shim_dependency_counts"]
    dependents = metrics["active_shim_dependents"]

    assert counts["app.agent"] >= 1
    assert counts["packages.runtime_core.kernel_host"] == 1
    assert "app/evals.py" not in dependents["app.agent"]
    assert "app/business_modules/office_module/module.py" in dependents["app.agent"]
    assert "app/main.py" not in dependents["packages.runtime_core.kernel_host"]
    assert "app/evals.py" not in dependents["packages.runtime_core.kernel_host"]
    assert "app/bootstrap/assemble.py" in dependents["packages.runtime_core.kernel_host"]
