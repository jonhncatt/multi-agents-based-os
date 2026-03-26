from __future__ import annotations

from app.contracts import ModuleManifest, TaskRequest
from app.kernel.host import KernelHost
from tests.support_agent_os import EchoBusinessModule


def test_kernel_dispatch_records_trace_for_business_module() -> None:
    kernel = KernelHost()
    office_module = EchoBusinessModule(
        manifest=ModuleManifest(
            module_id="office_module",
            module_kind="business",
            version="1.0.0",
            description="office dispatch target",
        ),
        text="handled",
    )
    kernel.register_module(office_module)
    kernel.init()

    response = kernel.dispatch(TaskRequest(task_id="req-1", task_type="chat", message="hello", context={"session_id": "s-1"}))

    assert response.ok is True
    snapshot = kernel.health_snapshot()
    trace = snapshot["recent_traces"][-1]
    assert trace["module_id"] == "office_module"
    assert trace["final_outcome"] == "ok"
