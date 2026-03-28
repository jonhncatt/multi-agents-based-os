from __future__ import annotations

from app.business_modules.research_module.pipeline.runtime import (
    aggregate_research_swarm_results,
    build_research_swarm_business_output,
)
from app.contracts import SwarmDegradationDecision, SwarmJoinSpec


def test_research_swarm_aggregator_deduplicates_and_marks_conflicts() -> None:
    join = SwarmJoinSpec(join_id="join-1", branch_ids=["branch-1", "branch-2", "branch-3"])
    aggregation = aggregate_research_swarm_results(
        join_spec=join,
        branch_results=[
            {
                "branch_id": "branch-1",
                "input_ref": "brief:architecture",
                "query": "conflict alpha",
                "ok": True,
                "top_source": {
                    "title": "Shared Research Conflict",
                    "url": "https://example.com/conflict-alpha",
                    "domain": "example.com",
                    "snippet": "Architecture branch source.",
                },
            },
            {
                "branch_id": "branch-2",
                "input_ref": "brief:runtime",
                "query": "conflict beta",
                "ok": True,
                "top_source": {
                    "title": "Shared Research Conflict",
                    "url": "https://example.com/conflict-beta",
                    "domain": "example.com",
                    "snippet": "Runtime branch source.",
                },
            },
            {
                "branch_id": "branch-3",
                "input_ref": "brief:runtime-copy",
                "query": "conflict beta copy",
                "ok": True,
                "top_source": {
                    "title": "Shared Research Conflict",
                    "url": "https://example.com/conflict-beta",
                    "domain": "example.com",
                    "snippet": "Duplicate runtime branch source.",
                },
            },
        ],
        degradation_decisions=[
            SwarmDegradationDecision(
                policy="serial_replay",
                trigger="branch_failed:branch-3",
                action="replay_failed_branch_sequentially",
            )
        ],
    )

    assert aggregation.degraded is True
    assert aggregation.degradation_reason == "serial_replay triggered for 1 branch(es)"
    assert len(aggregation.merged_items) == 2
    assert len(aggregation.conflicts) == 1
    assert aggregation.conflicts[0]["title"] == "Shared Research Conflict"


def test_research_swarm_business_output_is_readable_for_non_developers() -> None:
    join = SwarmJoinSpec(join_id="join-1", branch_ids=["branch-1", "branch-2", "branch-3"])
    degradation = [
        SwarmDegradationDecision(
            policy="serial_replay",
            trigger="branch_failed:branch-3",
            action="replay_failed_branch_sequentially",
            details={"branch_id": "branch-3"},
        )
    ]
    branch_results = [
        {
            "branch_id": "branch-1",
            "branch_label": "Architecture brief",
            "input_ref": "brief:architecture",
            "query": "conflict alpha",
            "ok": True,
            "source_count": 2,
            "sources": [
                {"title": "Shared Research Conflict", "url": "https://example.com/conflict-alpha", "domain": "example.com"}
            ],
            "top_source": {"title": "Shared Research Conflict", "url": "https://example.com/conflict-alpha"},
            "attempt_mode": "parallel",
            "result_grade": "success",
            "evidence_completeness": "complete",
            "reliability_note": "Evidence coverage is sufficient for a direct answer.",
        },
        {
            "branch_id": "branch-2",
            "branch_label": "Runtime brief",
            "input_ref": "brief:runtime",
            "query": "conflict beta",
            "ok": True,
            "source_count": 2,
            "sources": [
                {"title": "Shared Research Conflict", "url": "https://example.com/conflict-beta", "domain": "example.com"}
            ],
            "top_source": {"title": "Shared Research Conflict", "url": "https://example.com/conflict-beta"},
            "attempt_mode": "parallel",
            "result_grade": "success",
            "evidence_completeness": "complete",
            "reliability_note": "Evidence coverage is sufficient for a direct answer.",
        },
        {
            "branch_id": "branch-3",
            "branch_label": "Failure brief",
            "input_ref": "brief:degradation",
            "query": "branch failure note",
            "ok": True,
            "source_count": 1,
            "sources": [
                {"title": "Recovered Branch Finding", "url": "https://example.com/recovered-branch", "domain": "example.com"}
            ],
            "top_source": {"title": "Recovered Branch Finding", "url": "https://example.com/recovered-branch"},
            "attempt_mode": "serial_replay",
            "degraded": True,
            "result_grade": "success",
            "evidence_completeness": "complete",
            "reliability_note": "The branch recovered through serial replay.",
        },
    ]
    aggregation = aggregate_research_swarm_results(
        join_spec=join,
        branch_results=branch_results,
        degradation_decisions=degradation,
    )

    business = build_research_swarm_business_output(
        branch_results=branch_results,
        aggregation_result=aggregation,
        degradation_decisions=degradation,
    )

    assert "reviewed 3 branch(es)" in business["overall_summary"]["summary_text"]
    assert business["per_branch_evidence"][0]["branch_status"] == "success"
    assert business["per_branch_evidence"][2]["branch_status"] == "degraded"
    assert business["per_branch_evidence"][2]["included_in_final_merge"] is True
    assert business["conflict_and_degradation_notes"]["conflict_detected"] is True
    assert "Shared Research Conflict" in business["conflict_and_degradation_notes"]["conflict_summary"]
    assert business["conflict_and_degradation_notes"]["degraded_branches"][0]["branch_id"] == "branch-3"
