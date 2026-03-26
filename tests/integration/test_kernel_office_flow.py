from __future__ import annotations

from app.bootstrap import assemble_runtime
from app.config import load_config
from app.contracts import TaskRequest
from tests.support_agent_os import DummyLegacyHost


def test_kernel_dispatch_office_request_generates_trace() -> None:
    runtime = assemble_runtime(load_config(), legacy_host=DummyLegacyHost())

    response = runtime.dispatch(
        TaskRequest(
            task_id="integration-1",
            task_type="chat",
            message="hello",
            context={"history_turns": [], "summary": "", "session_id": "s-1"},
        ),
        module_id="office_module",
    )

    assert response.ok is True
    snapshot = runtime.kernel.health_snapshot()
    trace = snapshot["recent_traces"][-1]
    assert trace["module_id"] == "office_module"
    assert trace["final_outcome"] == "ok"
    assert "selected_tools" in trace and trace["selected_tools"]
