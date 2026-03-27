from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from app.codex_runner import build_codex_input_payload
from app.evolution import EvolutionStore
from app.openai_auth import normalize_model_for_auth_mode
from packages.agent_core import build_agent_capability_runtime


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
    "legacy_role_lab_runtime_snapshot",
    "legacy_tool_registry_snapshot",
]
