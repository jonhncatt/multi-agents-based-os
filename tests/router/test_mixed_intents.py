from __future__ import annotations

import pytest

from tests.router.support import run_pipeline


@pytest.mark.parametrize(
    ("message", "attachments"),
    [
        ("解释附件，再整理成表格后写成邮件", [{"inline_parseable": True, "needs_tooling": False}]),
        ("查出处，并给个修复建议", []),
        ("看 repo，再总结重点，再写 patch plan", []),
    ],
)
def test_mixed_intent_requests_use_planner(message: str, attachments: list[dict[str, object]]) -> None:
    result = run_pipeline(message=message, attachments=attachments)
    decision = result["decision"]
    route = result["route"]
    trace = result["trace"]

    assert decision.mixed_intent is True
    assert route["use_planner"] is True
    assert route["execution_policy"] in {"mixed_intent_planner_pipeline", "grounded_generation_pipeline"}
    assert trace.top_intent in {"understanding", "evidence", "generation"}
    assert len(trace.intent_candidates) >= 2
    assert trace.second_intent in {"generation", "understanding", "code_lookup", "evidence"}
    assert trace.chosen_execution_policy == route["execution_policy"]
