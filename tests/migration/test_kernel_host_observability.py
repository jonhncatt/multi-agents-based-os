from __future__ import annotations

import logging
from pathlib import Path

from app.bootstrap import assemble_runtime
from app.config import load_config
import packages.runtime_core.legacy_host_support as legacy_host_support_mod
from packages.runtime_core.legacy_host_support import (
    read_kernel_host_getattr_metrics,
    reset_kernel_host_getattr_metrics,
    run_primary_agent_chat_with_blackboard,
)
from tests.support_agent_os import DummyLegacyHost


class _DummyBlackboard:
    def __init__(self) -> None:
        self.started = False
        self.failed = ""
        self.completed: dict[str, object] = {}

    def start(self) -> None:
        self.started = True

    def complete(self, **payload: object) -> None:
        self.completed = dict(payload)

    def fail(self, error: str) -> None:
        self.failed = error


def test_kernel_host_getattr_records_access_and_warns_once(tmp_path: Path, monkeypatch, caplog) -> None:
    metrics_path = tmp_path / "kernel_host_getattr_accesses.json"
    monkeypatch.setattr(legacy_host_support_mod, "KERNEL_HOST_GETATTR_METRICS_PATH", metrics_path)
    reset_kernel_host_getattr_metrics()
    runtime = assemble_runtime(load_config())
    helper_surface = runtime.legacy_helper_surface()

    with caplog.at_level(logging.WARNING):
        helper_surface._build_followup_topic_hint(
            user_message="继续",
            history_turns=[
                {"role": "user", "text": "先在 repo 里找 validate_user 函数"},
                {"role": "assistant", "text": "我会先查找相关实现。"},
            ],
        )
        helper_surface._build_followup_topic_hint(
            user_message="继续",
            history_turns=[
                {"role": "user", "text": "先在 repo 里找 validate_user 函数"},
                {"role": "assistant", "text": "我会先查找相关实现。"},
            ],
        )

    metrics = read_kernel_host_getattr_metrics()
    snapshot = runtime.debug_kernel_host_snapshot()
    reset_kernel_host_getattr_metrics()

    assert metrics["fallback_access_counts"]["_build_followup_topic_hint"] == 2
    assert snapshot["compatibility_getattr"]["fallback_access_counts"]["_build_followup_topic_hint"] == 2
    warning_messages = [record.getMessage() for record in caplog.records]
    assert len([item for item in warning_messages if "_build_followup_topic_hint" in item]) == 1


def test_blackboard_orchestration_runs_through_helper_and_preserves_completion_shape() -> None:
    primary_agent = DummyLegacyHost(text="ok")
    blackboard = _DummyBlackboard()

    result = run_primary_agent_chat_with_blackboard(
        primary_agent=primary_agent,
        blackboard=blackboard,
        history_turns=[],
        summary="",
        user_message="hello",
        attachment_metas=[],
        settings={},
        session_id="s-1",
        route_state={},
        progress_cb=None,
    )

    assert blackboard.started is True
    assert blackboard.failed == ""
    assert blackboard.completed["effective_model"] == "gpt-test"
    assert blackboard.completed["route_state"]["top_intent"] == "understanding"
    assert blackboard.completed["execution_plan"] == ["router", "planner", "worker"]
    assert len(blackboard.completed["tool_events"]) == 0
    assert result[0] == "ok"
