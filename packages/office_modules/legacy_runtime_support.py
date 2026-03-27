from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path
from typing import Any

from app.codex_runner import build_codex_input_payload
from app.evolution import EvolutionStore
from app.models import ChatSettings
from app.openai_auth import normalize_model_for_auth_mode
from packages.agent_core import RoleContext, RoleResult, RunState, build_agent_capability_runtime


def compact_legacy_session(agent: Any, session: dict[str, Any], keep_last_turns: int) -> bool:
    turns = session.get("turns", [])
    if len(turns) <= agent.config.summary_trigger_turns:
        return False

    keep = max(2, min(2000, keep_last_turns))
    older = turns[:-keep]
    recent = turns[-keep:]
    if not older:
        return False

    existing_summary = session.get("summary", "")
    session["summary"] = agent._summarize_turns(existing_summary, older)
    session["turns"] = recent
    return True


def legacy_tool_registry_snapshot(agent: Any) -> dict[str, Any]:
    registry = agent._module_registry()
    module = getattr(registry, "tool_registry", None)
    selected_ref = str((registry.selected_refs or {}).get("tool_registry") or "")
    if module is None or not hasattr(module, "describe_tools"):
        return {
            "selected_ref": selected_ref,
            "tool_count": len(agent._lc_tools),
            "tools": [
                {
                    "name": str(getattr(tool, "name", "") or ""),
                    "description": str(getattr(tool, "description", "") or "")[:200],
                }
                for tool in agent._lc_tools
            ],
        }
    payload = module.describe_tools(agent=agent)
    if isinstance(payload, dict):
        payload.setdefault("selected_ref", selected_ref)
        return payload
    return {"selected_ref": selected_ref, "tool_count": len(agent._lc_tools)}


def legacy_role_lab_runtime_snapshot(agent: Any) -> dict[str, Any]:
    return agent._role_runtime_controller.runtime_snapshot()


def legacy_openai_auth_summary(agent: Any) -> dict[str, Any]:
    return agent._auth_manager.auth_summary()


def legacy_capability_bundle_snapshot(agent: Any) -> dict[str, Any]:
    metadata = agent._capability_runtime.metadata
    return {
        "module_paths": list(agent._capability_runtime.module_paths),
        "modules": list(metadata.get("modules") or []),
        "agent_modules": list(metadata.get("agent_modules") or []),
        "tool_modules": list(metadata.get("tool_modules") or []),
        "output_modules": list(metadata.get("output_modules") or []),
        "memory_modules": list(metadata.get("memory_modules") or []),
        "primary_agent_module": agent._selected_agent_module_id,
        "primary_tool_module": agent._selected_tool_module_id or metadata.get("primary_tool_module"),
        "primary_output_module": metadata.get("primary_output_module"),
        "primary_memory_module": metadata.get("primary_memory_module"),
        "extra_tool_modules": list(metadata.get("extra_tool_modules") or []),
        "role_sources": dict(metadata.get("role_sources") or {}),
    }


def legacy_capability_multi_module_snapshot(agent: Any) -> dict[str, Any]:
    runtime = build_agent_capability_runtime(
        agent.config,
        ["packages.office_modules", "packages.office_addons"],
    )
    return {
        "module_paths": list(runtime.module_paths),
        "module_count": len(runtime.bundles),
        "primary_tool_module": runtime.metadata.get("primary_tool_module"),
        "extra_tool_modules": list(runtime.metadata.get("extra_tool_modules") or []),
        "module_ids": [item.get("module_id") for item in runtime.metadata.get("modules") or []],
        "role_sources": dict(runtime.metadata.get("role_sources") or {}),
    }


def legacy_codex_input_payload(agent: Any, messages: list[dict[str, Any]]) -> dict[str, Any]:
    built_messages: list[Any] = []
    for item in messages:
        role = str(item.get("role") or "").strip().lower()
        content = item.get("content") or ""
        if role == "system":
            built_messages.append(agent._SystemMessage(content=content))
            continue
        if role == "user":
            built_messages.append(agent._HumanMessage(content=content))
            continue
        if role == "assistant":
            built_messages.append(
                agent._AIMessage(
                    content=content,
                    tool_calls=item.get("tool_calls") or [],
                )
            )
            continue
        if role == "tool":
            built_messages.append(
                agent._ToolMessage(
                    content=content,
                    tool_call_id=str(item.get("tool_call_id") or "call_missing"),
                    name=str(item.get("name") or ""),
                )
            )
    instructions, input_items = build_codex_input_payload(built_messages)
    return {"instructions": instructions, "input": input_items}


def legacy_normalize_model_for_auth(model: str, auth_mode: str) -> dict[str, Any]:
    return {"normalized_model": normalize_model_for_auth_mode(model, auth_mode)}


def legacy_kernel_module_snapshot(agent: Any) -> dict[str, Any]:
    snapshot = agent._kernel_runtime.health_snapshot()
    return {
        "active_manifest": dict(snapshot.active_manifest),
        "selected_modules": dict(snapshot.selected_modules),
        "module_health": dict(snapshot.module_health),
        "runtime_files": dict(snapshot.runtime_files),
    }


def legacy_evolution_overlay_snapshot(agent: Any) -> dict[str, Any]:
    store = EvolutionStore(agent.config.overlay_profile_path, agent.config.evolution_logs_dir)
    return store.runtime_payload(limit=6)


def legacy_evolution_turn_update() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="officetool-evolution-") as tmp_dir:
        base = Path(tmp_dir).resolve()
        store = EvolutionStore(base / "overlay_profile.json", base / "logs")
        event = store.record_turn(
            session_id="session-evolution-demo",
            user_message="请把这份 TCG 设计文档解释一下，并整理成表格后写成邮件。",
            assistant_text="我先解释整体设计，再给你一张表格，最后整理成邮件。",
            route_state={
                "primary_intent": "understanding",
                "task_type": "attachment_tooling",
                "execution_policy": "attachment_holistic_understanding_with_tools",
                "runtime_profile": "explainer",
            },
            answer_bundle={"summary": "TCG 设计文档整体思路与关键表格输出。", "citations": []},
            attachment_context_mode="explicit",
            attachment_count=1,
            settings={"response_style": "normal"},
            effective_model="gpt-5.1-chat",
            turn_count=2,
        )
        snapshot = store.runtime_payload(limit=4)
        overlay = dict(snapshot.get("overlay_profile") or {})
        module_affinity = dict(overlay.get("module_affinity") or {})
        return {
            "event": event,
            "overlay_profile": overlay,
            "recent_events": list(snapshot.get("recent_events") or []),
            "router_top_signal": str(((module_affinity.get("router") or [{}])[0] or {}).get("name") or ""),
            "finalizer_top_signal": str(((module_affinity.get("finalizer") or [{}])[0] or {}).get("name") or ""),
        }


def legacy_role_lab_multi_instance_batch(agent: Any) -> dict[str, Any]:
    registry_role = agent._role_registry.require("researcher")
    original_handler = registry_role.handler

    def _fake_researcher(current_agent: Any, *, context: RoleContext) -> RoleResult:
        spec = current_agent._make_role_spec(
            "researcher",
            description="多实例联网取证试运行。",
            output_keys=["summary", "bullets", "worker_hint", "queries", "scope", "stop_rules"],
        )
        suffix = str(context.extra.get("slot") or "").strip() or "slot"
        payload = {
            "summary": f"research batch {suffix}",
            "bullets": [f"处理 {suffix}", "已形成独立子任务结果。"],
            "worker_hint": f"整合 {suffix} 的结果。",
            "queries": [f"query-{suffix}"],
            "scope": "多实例试运行",
            "stop_rules": ["不要直接输出最终答案。"],
            "usage": current_agent._empty_usage(),
            "effective_model": current_agent.config.default_model,
            "notes": [],
        }
        return current_agent._make_role_result(spec, context, payload, json.dumps(payload, ensure_ascii=False))

    registry_role.handler = _fake_researcher
    try:
        run_state = RunState.create(
            run_id=f"role_lab_demo_{int(time.time() * 1000)}",
            session_id="session-role-lab-demo",
            task_type="role_lab_demo",
            root_role="coordinator",
            root_role_kind="processor",
            meta={"profile": "role_agent_lab"},
        )
        parent_node = run_state.root_node_id
        contexts: list[RoleContext] = []
        metas: list[dict[str, Any]] = []
        for slot in ("A", "B"):
            context = agent._make_role_context(
                "researcher",
                requested_model=agent.config.default_model,
                user_message=f"请并行搜索来源 {slot}",
                effective_user_message=f"请并行搜索来源 {slot}",
                history_summary="role-agent lab multi-instance demo",
                route={
                    "task_type": "web_research",
                    "primary_intent": "web",
                    "execution_policy": "web_research_full_pipeline",
                    "runtime_profile": "evidence",
                },
                extra={"slot": slot},
            )
            contexts.append(context)
            metas.append({"slot": slot})
        agent._role_runtime_controller.execute_batch(
            agent=agent,
            role="researcher",
            contexts=contexts,
            run_state=run_state,
            parent_node_id=parent_node,
            phase="multi_instance_demo",
            metas=metas,
            max_workers=2,
        )
        run_state.finish(status="completed")
        snapshot = agent._role_runtime_controller.capture_run_state(run_state)
        return {
            "ok": True,
            "stage4_readiness": agent._role_runtime_controller.stage4_readiness(),
            "runtime": snapshot,
            "instance_ids": [item.get("instance_id") for item in snapshot.get("instances") or []],
            "node_roles": [item.get("role") for item in snapshot.get("nodes") or []],
            "instance_count": int((snapshot.get("run") or {}).get("instance_count") or 0),
        }
    finally:
        registry_role.handler = original_handler


def legacy_role_lab_worker_branch_graph(agent: Any) -> dict[str, Any]:
    run_state = RunState.create(
        run_id=f"role_lab_worker_graph_{int(time.time() * 1000)}",
        session_id="session-role-lab-worker-graph",
        task_type="role_lab_worker_graph",
        root_role="coordinator",
        root_role_kind="processor",
        meta={"profile": "role_agent_lab"},
    )
    worker_execution = agent._role_runtime_controller.begin_managed(
        role="worker",
        run_state=run_state,
        parent_node_id=run_state.root_node_id,
        phase="attempt_1",
        tool_mode="uses_tools",
        meta={"attempt": 1, "debug": True},
    )
    branch_group = f"{worker_execution.node_id}:tool_batch:1"
    branch_ok = agent._role_runtime_controller.begin_task_node(
        run_state=run_state,
        role="worker",
        parent_node_id=worker_execution.node_id,
        phase="tool_call:read_text_file",
        role_kind="processor",
        node_type="branch",
        meta={"branch_group": branch_group, "tool_name": "read_text_file", "batch_index": 1},
    )
    agent._role_runtime_controller.complete_task_node(
        branch_ok,
        run_state=run_state,
        summary="read_text_file completed",
    )
    branch_retry = agent._role_runtime_controller.begin_task_node(
        run_state=run_state,
        role="worker",
        parent_node_id=worker_execution.node_id,
        phase="tool_call:search_web",
        role_kind="processor",
        node_type="branch",
        meta={"branch_group": branch_group, "tool_name": "search_web", "batch_index": 2},
    )
    agent._role_runtime_controller.begin_task_node(
        run_state=run_state,
        role="worker",
        parent_node_id=worker_execution.node_id,
        phase="tool_call:search_web",
        role_kind="processor",
        node_type="branch",
        meta={"branch_group": branch_group, "tool_name": "search_web", "batch_index": 2, "retry_attempt": 2},
        node_id=branch_retry,
    )
    agent._role_runtime_controller.fail_task_node(
        branch_retry,
        run_state=run_state,
        error="timeout while searching web",
        meta={"retry_count": 1},
    )
    join_node = agent._role_runtime_controller.begin_task_node(
        run_state=run_state,
        role="worker",
        parent_node_id=worker_execution.node_id,
        phase="tool_join",
        role_kind="processor",
        node_type="join",
        meta={"branch_group": branch_group, "branch_count": 2, "failed_branches": 1},
    )
    agent._role_runtime_controller.complete_task_node(
        join_node,
        run_state=run_state,
        summary="joined 2 tool branches",
        meta={"branch_group": branch_group, "branch_count": 2, "failed_branches": 1},
    )
    agent._role_runtime_controller.complete_managed(
        worker_execution,
        run_state=run_state,
        summary="worker graph demo completed",
    )
    run_state.finish(status="completed")
    snapshot = agent._role_runtime_controller.capture_run_state(run_state)
    nodes = list(snapshot.get("nodes") or [])
    return {
        "ok": True,
        "stage4_readiness": agent._role_runtime_controller.stage4_readiness(),
        "runtime": snapshot,
        "branch_node_count": sum(1 for item in nodes if str(item.get("node_type") or "") == "branch"),
        "join_node_count": sum(1 for item in nodes if str(item.get("node_type") or "") == "join"),
        "failed_branch_count": sum(
            1
            for item in nodes
            if str(item.get("node_type") or "") == "branch" and str(item.get("status") or "") == "failed"
        ),
    }


def legacy_route_runtime_override_attachment_context_requires_tooling(agent: Any) -> dict[str, Any]:
    base_route = agent._normalize_route_decision(
        {
            "task_type": "simple_understanding",
            "complexity": "low",
            "use_planner": False,
            "use_worker_tools": False,
            "use_reviewer": False,
            "use_revision": False,
            "use_structurer": False,
            "use_web_prefetch": False,
            "use_conflict_detector": False,
            "execution_policy": "attachment_understanding_direct",
            "primary_intent": "understanding",
            "reason": "debug_base_route",
            "summary": "debug base route",
        },
        fallback={"task_type": "simple_understanding"},
        settings=ChatSettings(enable_tools=True, response_style="short"),
    )
    route, raw, notes, actions = agent._apply_route_runtime_overrides(
        route=base_route,
        router_raw='{"source":"rules"}',
        user_message="请解释这个设计文档的整体思路",
        attachment_metas=[
            {
                "original_name": "spec.pdf",
                "suffix": ".pdf",
                "kind": "document",
                "size": 7340032,
            }
        ],
        settings=ChatSettings(enable_tools=True, response_style="short"),
        attachment_issues=["文档解析失败"],
        followup_has_attachments=False,
        followup_attachment_requires_tools=False,
        force_tool_followup=False,
    )
    return {"route": route, "router_raw": raw, "runtime_override_notes": notes, "runtime_override_actions": actions}


def legacy_route_runtime_override_force_tool_followup(agent: Any) -> dict[str, Any]:
    base_route = agent._normalize_route_decision(
        {
            "task_type": "simple_qa",
            "complexity": "low",
            "use_planner": False,
            "use_worker_tools": False,
            "use_reviewer": False,
            "use_revision": False,
            "use_structurer": False,
            "use_web_prefetch": False,
            "use_conflict_detector": False,
            "execution_policy": "qa_direct",
            "primary_intent": "qa",
            "reason": "debug_base_route",
            "summary": "debug base route",
        },
        fallback={"task_type": "simple_qa"},
        settings=ChatSettings(enable_tools=True, response_style="short"),
    )
    route, raw, notes, actions = agent._apply_route_runtime_overrides(
        route=base_route,
        router_raw='{"source":"rules"}',
        user_message="继续，直接去搜代码并执行",
        attachment_metas=[],
        settings=ChatSettings(enable_tools=True, response_style="short"),
        attachment_issues=[],
        followup_has_attachments=False,
        followup_attachment_requires_tools=False,
        force_tool_followup=True,
    )
    return {"route": route, "router_raw": raw, "runtime_override_notes": notes, "runtime_override_actions": actions}


__all__ = [
    "compact_legacy_session",
    "legacy_capability_bundle_snapshot",
    "legacy_capability_multi_module_snapshot",
    "legacy_codex_input_payload",
    "legacy_evolution_overlay_snapshot",
    "legacy_evolution_turn_update",
    "legacy_kernel_module_snapshot",
    "legacy_normalize_model_for_auth",
    "legacy_openai_auth_summary",
    "legacy_role_lab_multi_instance_batch",
    "legacy_role_lab_runtime_snapshot",
    "legacy_role_lab_worker_branch_graph",
    "legacy_route_runtime_override_attachment_context_requires_tooling",
    "legacy_route_runtime_override_force_tool_followup",
    "legacy_tool_registry_snapshot",
]
