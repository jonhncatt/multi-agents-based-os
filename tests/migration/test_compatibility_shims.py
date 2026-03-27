from __future__ import annotations

from pathlib import Path

from app.bootstrap import assemble_runtime
from app.config import load_config
from app.models import ChatSettings, ToolEvent
from packages.office_modules import execution_policy, intent_support, request_analysis, router_hints
from packages.runtime_core.legacy_host_support import (
    read_kernel_host_getattr_metrics,
    reset_kernel_host_getattr_metrics,
)
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


def test_legacy_agent_debug_helpers_remain_available_through_shim() -> None:
    reset_kernel_host_getattr_metrics()
    runtime = assemble_runtime(load_config())
    legacy = runtime.get_legacy_host()
    assert legacy is not None

    auth_summary = legacy._debug_openai_auth_summary()
    capability_snapshot = legacy._debug_capability_bundle_snapshot()
    kernel_snapshot = legacy._debug_kernel_module_snapshot()
    codex_payload = legacy._debug_codex_input_payload(
        [
            {"role": "system", "content": "You are a helper."},
            {"role": "user", "content": "hello"},
        ]
    )
    evolution_update = legacy._debug_evolution_turn_update()
    role_lab_batch = legacy._debug_role_lab_multi_instance_batch()
    role_lab_graph = legacy._debug_role_lab_worker_branch_graph()
    route_override_attachment = legacy._debug_route_runtime_override_attachment_context_requires_tooling()
    route_override_followup = legacy._debug_route_runtime_override_force_tool_followup()

    assert "available" in auth_summary
    assert "module_paths" in capability_snapshot
    assert "selected_modules" in kernel_snapshot
    assert "instructions" in codex_payload
    assert "input" in codex_payload
    assert "event" in evolution_update
    assert "overlay_profile" in evolution_update
    assert role_lab_batch["ok"] is True
    assert role_lab_batch["instance_count"] >= 1
    assert role_lab_graph["ok"] is True
    assert role_lab_graph["branch_node_count"] >= 1
    assert route_override_attachment["route"]["task_type"] == "attachment_tooling"
    assert route_override_attachment["route"]["use_worker_tools"] is True
    assert "runtime_override_actions" in route_override_attachment
    assert route_override_followup["route"]["use_worker_tools"] is True
    assert "runtime_override_actions" in route_override_followup
    metrics = read_kernel_host_getattr_metrics()
    reset_kernel_host_getattr_metrics()

    assert "_debug_kernel_module_snapshot" not in metrics["fallback_access_counts"]
    assert "_debug_tool_registry_snapshot" not in metrics["fallback_access_counts"]
    assert "_debug_role_contract_matrix" not in metrics["fallback_access_counts"]
    assert "_debug_capability_multi_module_snapshot" not in metrics["fallback_access_counts"]
    assert "_debug_route_runtime_override_attachment_context_requires_tooling" not in metrics["fallback_access_counts"]
    assert "_debug_route_runtime_override_force_tool_followup" not in metrics["fallback_access_counts"]


def test_legacy_host_route_helper_aliases_avoid_kernel_getattr_metrics() -> None:
    reset_kernel_host_getattr_metrics()
    runtime = assemble_runtime(load_config())
    legacy = runtime.get_legacy_host()
    assert legacy is not None

    route = legacy._route_request_by_rules(
        user_message="给我今天的新闻",
        attachment_metas=[],
        settings=ChatSettings(),
        route_state={},
        inline_followup_context=False,
    )
    route_state = legacy._build_session_route_state(route)
    normalized = legacy._normalize_route_decision_impl(
        route=route,
        fallback=route,
        settings=ChatSettings(),
    )
    metrics = read_kernel_host_getattr_metrics()
    reset_kernel_host_getattr_metrics()

    assert route["execution_policy"]
    assert isinstance(route_state, dict)
    assert normalized["execution_policy"]
    assert "_route_request_by_rules" not in metrics["fallback_access_counts"]
    assert "_build_session_route_state" not in metrics["fallback_access_counts"]
    assert "_normalize_route_decision_impl" not in metrics["fallback_access_counts"]


def test_legacy_host_office_helper_tail_aliases_avoid_kernel_getattr_metrics() -> None:
    reset_kernel_host_getattr_metrics()
    runtime = assemble_runtime(load_config())
    legacy = runtime.get_legacy_host()
    assert legacy is not None

    validation = legacy._summarize_validation_context(
        [
            ToolEvent(
                name="search_web",
                input={"query": "latest openai news"},
                output_preview='{"ok": true, "query": "latest openai news"}',
            )
        ]
    )
    hook_result = legacy._hook_before_route_finalize(
        route={
            "task_type": "simple_understanding",
            "primary_intent": "understanding",
            "execution_policy": "attachment_understanding_direct",
        },
        router_raw='{"source":"rules"}',
        planner_user_message="请解释这个设计文档的整体思路",
        attachment_issues=["文档解析失败"],
        followup_has_attachments=True,
        followup_attachment_requires_tools=True,
        attachment_metas=[
            {
                "original_name": "spec.pdf",
                "suffix": ".pdf",
                "kind": "document",
                "size": 7340032,
            }
        ],
        settings=ChatSettings(enable_tools=True, response_style="short"),
    )
    topic_hint = legacy._build_followup_topic_hint(
        user_message="上网查一下",
        history_turns=[
            {"role": "user", "text": "查一下大谷翔平最近在不在日本国内"},
            {"role": "assistant", "text": "先前答复错误地拒绝了这个请求。"},
        ],
    )
    force_tools = legacy._should_force_initial_tool_execution(
        "解释 workbench 文件夹下的两个函数 handle_route 和 run_chat",
        [],
    )
    metrics = read_kernel_host_getattr_metrics()
    reset_kernel_host_getattr_metrics()

    assert validation["web_tools_used"] is True
    assert hook_result.route["task_type"] == "simple_understanding"
    assert topic_hint
    assert force_tools is True
    assert "_summarize_validation_context" not in metrics["fallback_access_counts"]
    assert "_hook_before_route_finalize" not in metrics["fallback_access_counts"]
    assert "_build_followup_topic_hint" not in metrics["fallback_access_counts"]
    assert "_should_force_initial_tool_execution" not in metrics["fallback_access_counts"]
