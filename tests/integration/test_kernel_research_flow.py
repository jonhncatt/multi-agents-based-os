from __future__ import annotations

from app.bootstrap import AgentOSAssembleConfig, assemble_runtime
from app.config import load_config
from app.contracts import TaskRequest
from tests.support_agent_os import bind_fake_research_provider


def test_kernel_dispatch_research_request_generates_trace() -> None:
    runtime = assemble_runtime(
        load_config(),
        assemble_config=AgentOSAssembleConfig(
            include_research_module=True,
            include_coding_module=False,
            include_adaptation_module=False,
            enable_session_provider=True,
        ),
    )
    bind_fake_research_provider(runtime)

    response = runtime.dispatch(
        TaskRequest(
            task_id="research-integration-1",
            task_type="task.research",
            message="multi source research demo",
            context={
                "session_id": "research-integration",
                "fetch_top_result": True,
                "execution_policy": "research_pipeline",
                "runtime_profile": "research_demo",
            },
        ),
        module_id="research_module",
    )

    assert response.ok is True
    trace = runtime.kernel.health_snapshot()["recent_traces"][-1]
    assert trace["module_id"] == "research_module"
    assert trace["final_outcome"] == "ok"
    assert trace["execution_policy"] == "research_pipeline"
    assert trace["runtime_profile"] == "research_demo"
    assert trace["selected_tools"] == ["web.search", "web.fetch"]
    assert trace["selected_providers"] == ["fake_research_provider"]
    assert any(event["stage"] == "tool_dispatch" for event in trace["events"])
