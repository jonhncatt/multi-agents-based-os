from __future__ import annotations

import pytest

from tests.router.support import run_pipeline


@pytest.mark.parametrize(
    "message",
    [
        "嗯",
        "这个呢",
        "you see this?",
    ],
)
def test_low_confidence_requests_go_to_safe_clarifying_route(message: str) -> None:
    result = run_pipeline(message=message)
    decision = result["decision"]
    route = result["route"]
    trace = result["trace"]

    assert decision.confidence < 0.60
    assert decision.requires_clarifying_route is True
    assert route["execution_policy"] == "standard_safe_pipeline"
    assert route["use_planner"] is True
    assert route["use_reviewer"] is True
    assert trace.requires_clarifying_route is True
    assert trace.chosen_execution_policy == "standard_safe_pipeline"
    assert trace.llm_escalated is False


def test_ambiguous_attachment_request_does_not_fall_into_direct_answer() -> None:
    result = run_pipeline(
        message="这个呢",
        attachments=[{"inline_parseable": True, "needs_tooling": False}],
    )
    route = result["route"]
    trace = result["trace"]

    assert route["execution_policy"] != "understanding_direct"
    assert route["execution_policy"] != "direct_generation"
    assert trace.chosen_execution_policy == route["execution_policy"]
