from __future__ import annotations

from pathlib import Path

from app.bootstrap import AgentOSAssembleConfig, assemble_runtime
from app.business_modules.research_module.manifest import RESEARCH_MODULE_MANIFEST
from app.config import load_config
from app.contracts import TaskRequest
from tests.support_agent_os import bind_fake_research_provider


def test_research_module_runs_via_kernel_and_uses_formal_tools() -> None:
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
            task_id="research-1",
            task_type="task.research",
            message="agent os module boundaries",
            context={"session_id": "research-session", "fetch_top_result": True},
        ),
        module_id="research_module",
    )

    assert response.ok is True
    assert response.payload["module_id"] == "research_module"
    assert response.payload["selected_tools"] == ["web.search", "web.fetch"]
    assert response.payload["selected_providers"] == ["fake_research_provider"]
    assert response.payload["research"]["source_count"] == 2
    assert response.payload["module_pipeline"][0]["stage"] == "dispatch"
    assert "Fetched evidence" in response.text


def test_research_module_manifest_and_metadata_are_formalized() -> None:
    runtime = assemble_runtime(load_config())
    tool_contracts = runtime.kernel.health_snapshot()["registry"]["tool_contracts"]

    for tool_name in RESEARCH_MODULE_MANIFEST.required_tools:
        assert tool_name in tool_contracts

    assert RESEARCH_MODULE_MANIFEST.compatibility_level == "native"
    assert RESEARCH_MODULE_MANIFEST.owner == "research-agent-os"
    assert "task.research.swarm" in RESEARCH_MODULE_MANIFEST.capabilities
    assert Path("app/business_modules/research_module/module.json").is_file()
