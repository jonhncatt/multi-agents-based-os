from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from threading import Lock
from typing import Any

from packages.runtime_core.blackboard import Blackboard

REPO_ROOT = Path(__file__).resolve().parents[2]
KERNEL_HOST_GETATTR_METRICS_PATH = REPO_ROOT / "artifacts" / "platform_metrics" / "kernel_host_getattr_accesses.json"
_KERNEL_HOST_GETATTR_METRICS_LOCK = Lock()
_KERNEL_HOST_GETATTR_METRICS_CACHE: dict[str, Any] | None = None


def build_primary_agent(
    *,
    config: Any,
    kernel_runtime: Any,
    capability_runtime: Any,
    tool_executor: Any,
    host: Any,
) -> Any:
    primary_agent_module = capability_runtime.primary_agent_module
    if primary_agent_module is None:
        raise RuntimeError("No AgentModule is available in capability runtime")
    builder = primary_agent_module.build_runtime
    if builder is None:
        raise RuntimeError(f"AgentModule {primary_agent_module.module_id} does not expose build_runtime")
    return builder(
        config=config,
        kernel_runtime=kernel_runtime,
        capability_runtime=capability_runtime,
        tool_executor=tool_executor,
        host=host,
    )


def create_blackboard(
    *,
    session_id: str | None,
    user_message: str,
    attachment_metas: list[dict[str, Any]] | None,
    primary_agent_module: Any,
    primary_tool_module: Any,
    primary_output_module: Any,
    primary_memory_module: Any,
    capability_runtime: Any,
) -> Blackboard:
    return Blackboard.create(
        session_id=session_id,
        user_message=user_message,
        attachment_ids=[
            str((item or {}).get("id") or "").strip()
            for item in (attachment_metas or [])
            if str((item or {}).get("id") or "").strip()
        ],
        selected_agent_module_id=primary_agent_module.module_id,
        selected_tool_module_id=primary_tool_module.module_id,
        selected_output_module_id=primary_output_module.module_id if primary_output_module else "",
        selected_memory_module_id=primary_memory_module.module_id if primary_memory_module else "",
        selected_capability_modules=[item.module_id for item in capability_runtime.bundles],
    )


def _default_kernel_host_getattr_metrics() -> dict[str, Any]:
    return {
        "updated_at": "",
        "fallback_access_counts": {},
    }


def _load_kernel_host_getattr_metrics() -> dict[str, Any]:
    global _KERNEL_HOST_GETATTR_METRICS_CACHE
    if _KERNEL_HOST_GETATTR_METRICS_CACHE is not None:
        return _KERNEL_HOST_GETATTR_METRICS_CACHE
    if KERNEL_HOST_GETATTR_METRICS_PATH.exists():
        try:
            loaded = json.loads(KERNEL_HOST_GETATTR_METRICS_PATH.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                metrics = _default_kernel_host_getattr_metrics()
                metrics.update(loaded)
                metrics["fallback_access_counts"] = dict(metrics.get("fallback_access_counts") or {})
                _KERNEL_HOST_GETATTR_METRICS_CACHE = metrics
                return metrics
        except (OSError, ValueError, TypeError):
            pass
    _KERNEL_HOST_GETATTR_METRICS_CACHE = _default_kernel_host_getattr_metrics()
    return _KERNEL_HOST_GETATTR_METRICS_CACHE


def _persist_kernel_host_getattr_metrics(metrics: dict[str, Any]) -> None:
    KERNEL_HOST_GETATTR_METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    KERNEL_HOST_GETATTR_METRICS_PATH.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")


def record_kernel_host_getattr_access(name: str) -> bool:
    with _KERNEL_HOST_GETATTR_METRICS_LOCK:
        metrics = _load_kernel_host_getattr_metrics()
        counts = metrics["fallback_access_counts"]
        counts[name] = int(counts.get(name) or 0) + 1
        metrics["updated_at"] = datetime.now(timezone.utc).isoformat()
        _persist_kernel_host_getattr_metrics(metrics)
        return counts[name] == 1


def read_kernel_host_getattr_metrics() -> dict[str, Any]:
    with _KERNEL_HOST_GETATTR_METRICS_LOCK:
        metrics = _load_kernel_host_getattr_metrics()
        return {
            "updated_at": str(metrics.get("updated_at") or ""),
            "fallback_access_counts": dict(metrics.get("fallback_access_counts") or {}),
        }


def reset_kernel_host_getattr_metrics() -> None:
    global _KERNEL_HOST_GETATTR_METRICS_CACHE
    with _KERNEL_HOST_GETATTR_METRICS_LOCK:
        _KERNEL_HOST_GETATTR_METRICS_CACHE = _default_kernel_host_getattr_metrics()
        if KERNEL_HOST_GETATTR_METRICS_PATH.exists():
            KERNEL_HOST_GETATTR_METRICS_PATH.unlink()


def complete_blackboard(blackboard: Blackboard, result: Any) -> None:
    from packages.office_modules.execution_runtime import normalize_legacy_run_chat_result

    normalized = normalize_legacy_run_chat_result(result)
    blackboard.complete(
        effective_model=normalized.effective_model,
        route_state=normalized.route_state,
        execution_plan=normalized.execution_plan,
        execution_trace=normalized.execution_trace,
        tool_events=normalized.tool_events,
        answer_bundle=normalized.answer_bundle,
    )


def run_primary_agent_chat_with_blackboard(
    *,
    primary_agent: Any,
    blackboard: Blackboard,
    history_turns: list[dict[str, Any]],
    summary: str,
    user_message: str,
    attachment_metas: list[dict[str, Any]],
    settings: Any,
    session_id: str | None = None,
    route_state: dict[str, Any] | None = None,
    progress_cb: Any | None = None,
) -> Any:
    blackboard.start()
    try:
        result = primary_agent.run_chat(
            history_turns,
            summary,
            user_message,
            attachment_metas,
            settings,
            session_id=session_id,
            route_state=route_state,
            progress_cb=progress_cb,
            blackboard=blackboard,
        )
        complete_blackboard(blackboard, result)
        return result
    except Exception as exc:
        blackboard.fail(str(exc))
        raise


def kernel_host_snapshot(
    *,
    agent_modules: tuple[Any, ...],
    primary_agent_module: Any,
    tool_modules: tuple[Any, ...],
    primary_tool_module: Any,
    output_modules: tuple[Any, ...],
    primary_output_module: Any,
    memory_modules: tuple[Any, ...],
    primary_memory_module: Any,
    capability_runtime: Any,
    blackboard: Blackboard | None,
    getattr_metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "agent_modules": [
            {
                "module_id": item.module_id,
                "title": item.title,
                "description": item.description,
                "roles": list(item.roles),
                "profiles": list(item.profiles),
            }
            for item in agent_modules
        ],
        "primary_agent_module": {
            "module_id": primary_agent_module.module_id,
            "title": primary_agent_module.title,
            "description": primary_agent_module.description,
            "roles": list(primary_agent_module.roles),
            "profiles": list(primary_agent_module.profiles),
        }
        if primary_agent_module
        else {},
        "tool_modules": [
            {
                "module_id": item.module_id,
                "title": item.title,
                "description": item.description,
                "tool_names": list(item.tool_names),
                "group": str(item.metadata.get("group") or ""),
            }
            for item in tool_modules
        ],
        "primary_tool_module": {
            "module_id": primary_tool_module.module_id,
            "title": primary_tool_module.title,
            "description": primary_tool_module.description,
            "tool_names": list(primary_tool_module.tool_names),
        }
        if primary_tool_module
        else {},
        "output_modules": [
            {
                "module_id": item.module_id,
                "title": item.title,
                "description": item.description,
                "output_kinds": list(item.output_kinds),
            }
            for item in output_modules
        ],
        "memory_modules": [
            {
                "module_id": item.module_id,
                "title": item.title,
                "description": item.description,
                "signal_kinds": list(item.signal_kinds),
            }
            for item in memory_modules
        ],
        "primary_output_module": {
            "module_id": primary_output_module.module_id,
            "title": primary_output_module.title,
            "description": primary_output_module.description,
            "output_kinds": list(primary_output_module.output_kinds),
        }
        if primary_output_module
        else {},
        "primary_memory_module": {
            "module_id": primary_memory_module.module_id,
            "title": primary_memory_module.title,
            "description": primary_memory_module.description,
            "signal_kinds": list(primary_memory_module.signal_kinds),
        }
        if primary_memory_module
        else {},
        "capability_modules": list(capability_runtime.metadata.get("module_paths") or []),
        "loaded_capability_bundles": [item.get("module_id") for item in capability_runtime.metadata.get("modules") or []],
        "tool_dispatch_modules": list(capability_runtime.metadata.get("tool_dispatch_modules") or []),
        "role_sources": dict(capability_runtime.metadata.get("role_sources") or {}),
        "blackboard": blackboard.snapshot() if blackboard else {},
        "compatibility_getattr": dict(getattr_metrics or {}),
    }


__all__ = [
    "build_primary_agent",
    "complete_blackboard",
    "create_blackboard",
    "kernel_host_snapshot",
    "read_kernel_host_getattr_metrics",
    "record_kernel_host_getattr_access",
    "reset_kernel_host_getattr_metrics",
    "run_primary_agent_chat_with_blackboard",
]
