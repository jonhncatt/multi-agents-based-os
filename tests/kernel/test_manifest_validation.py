from __future__ import annotations

import pytest

from app.contracts import CompatibilityError, ModuleManifest, TaskRequest
from app.kernel.host import KernelHost
from tests.support_agent_os import EchoBusinessModule


def test_invalid_manifest_is_rejected() -> None:
    kernel = KernelHost(kernel_version="1.0.0")
    module = EchoBusinessModule(
        manifest=ModuleManifest(
            module_id="future_module",
            module_kind="business",
            version="1.0.0",
            description="future",
            min_kernel_version="9.0.0",
        ),
        text="future",
    )

    with pytest.raises(CompatibilityError):
        kernel.register_module(module)


def test_healthcheck_failure_marks_module_unhealthy() -> None:
    kernel = KernelHost()
    module = EchoBusinessModule(
        manifest=ModuleManifest(
            module_id="bad_module",
            module_kind="business",
            version="1.0.0",
            description="bad",
        ),
        text="bad",
        healthy=False,
    )
    kernel.register_module(module)
    kernel.init()

    snapshot = kernel.health_snapshot()
    assert snapshot["registry"]["module_states"]["bad_module"]["health_status"] == "unhealthy"


def test_module_rollback_restores_previous_version() -> None:
    kernel = KernelHost()
    module_v1 = EchoBusinessModule(
        manifest=ModuleManifest(module_id="office_module", module_kind="business", version="1.0.0", description="v1"),
        text="v1",
    )
    module_v2 = EchoBusinessModule(
        manifest=ModuleManifest(module_id="office_module", module_kind="business", version="1.1.0", description="v2"),
        text="v2",
    )

    kernel.register_module(module_v1)
    kernel.init()
    kernel.hot_swap_module(module_v2)
    rollback = kernel.rollback_module("office_module")

    assert rollback["ok"] is True
    response = kernel.dispatch(TaskRequest(task_id="req-2", task_type="chat", message="hello"))
    assert response.text == "v1"
