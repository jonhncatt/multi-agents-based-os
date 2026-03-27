from __future__ import annotations

from app.bootstrap import AgentOSAssembleConfig, assemble_runtime
from app.config import load_config
from app.contracts import TaskRequest
from tests.support_agent_os import bind_fake_research_provider


def test_kernel_dispatch_research_swarm_request_handles_serial_replay_and_join_trace() -> None:
    runtime = assemble_runtime(
        load_config(),
        assemble_config=AgentOSAssembleConfig(
            include_research_module=True,
            include_coding_module=False,
            include_adaptation_module=False,
            enable_session_provider=True,
        ),
    )
    bind_fake_research_provider(runtime, fail_once_queries={"branch failure note"}, fallback_providers=[])

    response = runtime.dispatch(
        TaskRequest(
            task_id="research-swarm-1",
            task_type="task.research",
            message="run research swarm",
            context={
                "session_id": "research-swarm-session",
                "execution_policy": "research_swarm_pipeline",
                "runtime_profile": "research_swarm_demo",
                "swarm_mode": "parallel_research",
                "swarm_inputs": [
                    {"label": "Architecture brief", "query": "conflict alpha", "input_ref": "brief:architecture"},
                    {"label": "Runtime brief", "query": "conflict beta", "input_ref": "brief:runtime"},
                    {"label": "Failure brief", "query": "branch failure note", "input_ref": "brief:degradation"},
                ],
            },
        ),
        module_id="research_module",
    )

    assert response.ok is True
    swarm = dict(response.payload.get("swarm") or {})
    assert swarm["branch_count"] == 3
    assert swarm["degradation"]["degraded"] is True
    assert len(swarm["aggregation"]["conflicts"]) >= 1
    assert any(item["attempt_mode"] == "serial_replay" for item in swarm["branches"])
    assert "serial replay was triggered" in response.text.lower()

    trace = runtime.kernel.health_snapshot()["recent_traces"][-1]
    assert trace["module_id"] == "research_module"
    assert trace["execution_policy"] == "research_swarm_pipeline"
    assert trace["runtime_profile"] == "research_swarm_demo"
    assert trace["selected_roles"] == ["researcher", "aggregator"]
    assert trace["selected_tools"] == ["web.search", "web.fetch"]
    assert trace["selected_providers"] == ["fake_research_provider"]
    stages = [event["stage"] for event in trace["events"]]
    assert "swarm_branch_plan" in stages
    assert "swarm_branch_result" in stages
    assert "swarm_degradation" in stages
    assert "swarm_join" in stages
