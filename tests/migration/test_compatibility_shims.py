from __future__ import annotations

from pathlib import Path

from app.bootstrap import assemble_runtime
from app.config import load_config
from packages.office_modules import execution_policy, intent_support, request_analysis, router_hints
from app.business_modules.office_module.manifest import OFFICE_MODULE_COMPATIBILITY_SHIMS


def test_compatibility_shim_markers_exist() -> None:
    assert OFFICE_MODULE_COMPATIBILITY_SHIMS


def test_legacy_imports_and_placeholder_docs_remain_available() -> None:
    runtime = assemble_runtime(load_config())
    legacy = runtime.get_legacy_host()
    assert legacy is not None
    assert hasattr(legacy, "run_chat")
    assert Path("packages/agent-core/README.md").is_file()
    assert Path("packages/office-modules/README.md").is_file()
    assert Path("packages/runtime-core/README.md").is_file()


def test_retired_router_rules_shim_is_replaced_by_canonical_router_hints() -> None:
    assert Path("app/router_rules.py").exists() is False
    assert hasattr(router_hints, "SOURCE_TRACE_HINTS")
    assert hasattr(router_hints, "text_has_any")


def test_retired_request_and_intent_support_shims_are_replaced_by_canonical_packages() -> None:
    assert Path("app/request_analysis_support.py").exists() is False
    assert Path("app/router_intent_support.py").exists() is False
    assert hasattr(request_analysis, "looks_like_local_code_lookup_request")
    assert hasattr(intent_support, "looks_like_understanding_request")


def test_retired_execution_policy_shim_is_replaced_by_canonical_package() -> None:
    assert Path("app/execution_policy.py").exists() is False
    assert hasattr(execution_policy, "execution_policy_spec")
    assert hasattr(execution_policy, "planner_enabled_for_policy")
