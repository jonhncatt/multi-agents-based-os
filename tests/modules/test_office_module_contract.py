from __future__ import annotations

from pathlib import Path

from app.bootstrap import AgentOSAssembleConfig, assemble_runtime
from app.business_modules.office_module.manifest import OFFICE_MODULE_COMPATIBILITY_SHIMS, OFFICE_MODULE_MANIFEST
from app.config import load_config
from app.contracts import TaskRequest
from tests.support_agent_os import DummyLegacyHost


def test_office_module_runs_via_kernel_and_emits_module_metadata() -> None:
    runtime = assemble_runtime(
        load_config(),
        legacy_host=DummyLegacyHost(),
        assemble_config=AgentOSAssembleConfig(
            include_research_module=False,
            include_coding_module=False,
            include_adaptation_module=False,
            enable_session_provider=True,
        ),
    )

    response = runtime.dispatch(
        TaskRequest(
            task_id="office-1",
            task_type="chat",
            message="hello",
            context={"history_turns": [], "summary": "", "session_id": "s-1"},
        ),
        module_id="office_module",
    )

    assert response.ok is True
    assert response.payload["module_id"] == "office_module"
    assert response.payload["module_pipeline"][0]["role"] == "router"
    assert response.payload["compatibility_shims"] == list(OFFICE_MODULE_COMPATIBILITY_SHIMS)


def test_office_module_manifest_and_tool_contracts_are_registered() -> None:
    runtime = assemble_runtime(load_config(), legacy_host=DummyLegacyHost())
    tool_contracts = runtime.kernel.health_snapshot()["registry"]["tool_contracts"]

    for tool_name in OFFICE_MODULE_MANIFEST.required_tools:
        assert tool_name in tool_contracts

    assert OFFICE_MODULE_MANIFEST.compatibility_level == "shim"
    assert Path("app/business_modules/office_module/module.json").is_file()
