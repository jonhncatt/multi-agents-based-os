from __future__ import annotations

import pytest

from tests.router.support import run_pipeline


@pytest.mark.parametrize(
    ("message", "enable_tools"),
    [
        ("帮我基于这个 repo 改一下实现", True),
        ("根据这个函数出处给我修复建议", True),
        ("Based on this repo function, patch the implementation", False),
    ],
)
def test_grounded_generation_enables_review_chain(message: str, enable_tools: bool) -> None:
    result = run_pipeline(message=message, enable_tools=enable_tools)
    decision = result["decision"]
    route = result["route"]
    trace = result["trace"]

    assert decision.requires_grounding is True
    assert route["execution_policy"] == "grounded_generation_pipeline"
    assert route["use_reviewer"] is True
    assert route["use_revision"] is True
    assert trace.chosen_execution_policy == "grounded_generation_pipeline"
    assert trace.reviewer_enabled is True
    assert trace.revision_enabled is True
