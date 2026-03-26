from __future__ import annotations

from app.intent_schema import ConversationFrame, IntentDecision, RequestSignals
from app.route_verifier import RouteVerifier


def test_verifier_enables_planner_for_mixed_intent() -> None:
    verifier = RouteVerifier()
    route, _ = verifier.verify(
        decision=IntentDecision(top_intent="understanding", second_intent="generation", mixed_intent=True),
        route={"execution_policy": "mixed_intent_planner_pipeline", "use_planner": False},
        signals=RequestSignals(),
        frame=ConversationFrame(),
    )
    assert route["use_planner"] is True
    assert "force_enable_planner" in route["verifier_actions"]


def test_verifier_enables_worker_tools_when_required() -> None:
    verifier = RouteVerifier()
    route, _ = verifier.verify(
        decision=IntentDecision(top_intent="code_lookup", requires_tools=True),
        route={"execution_policy": "code_lookup_with_tools", "use_worker_tools": False},
        signals=RequestSignals(),
        frame=ConversationFrame(),
    )
    assert route["use_worker_tools"] is True
    assert "force_enable_worker_tools" in route["verifier_actions"]


def test_verifier_does_not_rewrite_plain_understanding_route() -> None:
    verifier = RouteVerifier()
    route, _ = verifier.verify(
        decision=IntentDecision(top_intent="understanding"),
        route={
            "task_type": "understanding",
            "execution_policy": "understanding_direct",
            "use_planner": False,
            "use_worker_tools": False,
        },
        signals=RequestSignals(),
        frame=ConversationFrame(dominant_intent="understanding"),
    )
    assert route["execution_policy"] == "understanding_direct"
    assert route["verifier_actions"] == []
