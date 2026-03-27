from __future__ import annotations

from app.business_modules.research_module.pipeline.runtime import aggregate_research_swarm_results
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
