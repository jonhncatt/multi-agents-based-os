from __future__ import annotations

import pytest

from tests.router.support import run_pipeline


@pytest.mark.parametrize(
    ("message", "route_state"),
    [
        (
            "继续",
            {"primary_intent": "understanding", "execution_policy": "understanding_direct"},
        ),
        (
            "按刚才那个改成表格",
            {"primary_intent": "understanding", "execution_policy": "understanding_direct"},
        ),
        (
            "翻成日文",
            {"primary_intent": "understanding", "execution_policy": "understanding_direct"},
        ),
        (
            "再简短一点",
            {"primary_intent": "understanding", "execution_policy": "understanding_direct"},
        ),
    ],
)
def test_followup_requests_inherit_previous_intent(message: str, route_state: dict[str, str]) -> None:
    result = run_pipeline(
        message=message,
        route_state=route_state,
        inline_followup_context=True,
    )
    frame = result["frame"]
    decision = result["decision"]
    route = result["route"]
    trace = result["trace"]

    assert frame.dominant_intent == "understanding"
    assert decision.inherited_from_state == "understanding"
    assert route["execution_policy"] != "standard_safe_pipeline"
    assert trace.top_intent in {"understanding", "generation"}
    assert trace.chosen_execution_policy != "standard_safe_pipeline"
    assert trace.second_intent in {"", "generation", "understanding"}
    assert trace.llm_escalated is False
