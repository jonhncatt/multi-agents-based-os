from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.contracts import SwarmAggregationResult, SwarmBranchSpec, SwarmDegradationDecision, SwarmJoinSpec


def build_research_pipeline_trace(
    *,
    query: str,
    search_count: int,
    fetch_attempted: bool,
    fetch_ok: bool,
) -> list[dict[str, Any]]:
    trace = [
        {
            "stage": "dispatch",
            "detail": "KernelHost resolved research_module.",
            "status": "complete",
        },
        {
            "stage": "search_sources",
            "detail": f"research_module searched sources for query={query!r}.",
            "status": "complete" if search_count > 0 else "error",
            "count": int(search_count),
        },
    ]
    if fetch_attempted:
        trace.append(
            {
                "stage": "fetch_top_source",
                "detail": "research_module fetched the top source for evidence preview.",
                "status": "complete" if fetch_ok else "error",
            }
        )
    trace.append(
        {
            "stage": "compose_response",
            "detail": "research_module composed the investigation summary.",
            "status": "complete" if search_count > 0 else "error",
        }
    )
    return trace


def aggregate_research_swarm_results(
    *,
    join_spec: SwarmJoinSpec,
    branch_results: list[dict[str, Any]],
    degradation_decisions: list[SwarmDegradationDecision] | None = None,
) -> SwarmAggregationResult:
    degradation_decisions = degradation_decisions or []
    merged_index: dict[str, dict[str, Any]] = {}
    title_variants: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for result in branch_results:
        if not bool(result.get("ok")):
            continue
        top_source = dict(result.get("top_source") or {})
        if not top_source:
            continue
        title = str(top_source.get("title") or "Untitled source").strip() or "Untitled source"
        url = str(top_source.get("url") or "").strip()
        domain = str(top_source.get("domain") or "").strip()
        snippet = str(top_source.get("snippet") or "").strip()
        merge_key = url or title.lower()
        item = merged_index.get(merge_key)
        if item is None:
            item = {
                "title": title,
                "url": url,
                "domain": domain,
                "snippet": snippet,
                "branch_ids": [str(result.get("branch_id") or "")],
                "input_refs": [str(result.get("input_ref") or "")],
                "queries": [str(result.get("query") or "")],
            }
            merged_index[merge_key] = item
        else:
            branch_id = str(result.get("branch_id") or "")
            input_ref = str(result.get("input_ref") or "")
            query = str(result.get("query") or "")
            if branch_id and branch_id not in item["branch_ids"]:
                item["branch_ids"].append(branch_id)
            if input_ref and input_ref not in item["input_refs"]:
                item["input_refs"].append(input_ref)
            if query and query not in item["queries"]:
                item["queries"].append(query)
            if not item.get("snippet") and snippet:
                item["snippet"] = snippet
        title_key = title.lower()
        title_variants[title_key].append(
            {
                "title": title,
                "url": url,
                "branch_id": str(result.get("branch_id") or ""),
                "input_ref": str(result.get("input_ref") or ""),
            }
        )

    conflicts: list[dict[str, Any]] = []
    for title_key, items in title_variants.items():
        unique_urls = sorted({str(item.get("url") or "").strip() for item in items if str(item.get("url") or "").strip()})
        if len(unique_urls) <= 1:
            continue
        conflicts.append(
            {
                "title": items[0].get("title") or title_key,
                "urls": unique_urls,
                "branch_ids": sorted({str(item.get("branch_id") or "") for item in items if str(item.get("branch_id") or "").strip()}),
                "input_refs": sorted({str(item.get("input_ref") or "") for item in items if str(item.get("input_ref") or "").strip()}),
            }
        )

    result = SwarmAggregationResult(
        join_id=join_spec.join_id,
        summary=(
            f"Aggregator merged {len(merged_index)} unique findings from {len(branch_results)} branch(es) "
            f"and marked {len(conflicts)} conflict(s)."
        ),
        merged_items=list(merged_index.values()),
        conflicts=conflicts,
        degraded=bool(degradation_decisions),
        degradation_reason=(
            f"serial_replay triggered for {len(degradation_decisions)} branch(es)"
            if degradation_decisions
            else ""
        ),
    )
    return result


def build_research_swarm_pipeline_trace(
    *,
    swarm_run_id: str,
    branch_specs: list[SwarmBranchSpec],
    branch_results: list[dict[str, Any]],
    join_spec: SwarmJoinSpec,
    aggregation_result: SwarmAggregationResult,
    degradation_decisions: list[SwarmDegradationDecision],
) -> list[dict[str, Any]]:
    trace: list[dict[str, Any]] = [
        {
            "stage": "dispatch",
            "detail": "KernelHost resolved research_module for Swarm MVP execution.",
            "status": "complete",
            "swarm_run_id": swarm_run_id,
        },
        {
            "stage": "swarm_branch_plan",
            "detail": f"research_module planned {len(branch_specs)} branch(es) for parallel research.",
            "status": "complete",
            "branch_count": len(branch_specs),
            "join_id": join_spec.join_id,
        },
    ]
    for result in branch_results:
        trace.append(
            {
                "stage": "swarm_branch_result",
                "detail": (
                    f"{result.get('branch_label') or result.get('branch_id')}: "
                    f"{result.get('source_count', 0)} source(s) gathered"
                ),
                "status": "complete" if bool(result.get("ok")) else "error",
                "branch_id": str(result.get("branch_id") or ""),
                "input_ref": str(result.get("input_ref") or ""),
                "attempt_mode": str(result.get("attempt_mode") or "parallel"),
            }
        )
    for decision in degradation_decisions:
        trace.append(
            {
                "stage": "swarm_degradation",
                "detail": f"{decision.policy} triggered by {decision.trigger}.",
                "status": "warning",
                "policy": decision.policy,
                "trigger": decision.trigger,
                "action": decision.action,
            }
        )
    trace.append(
        {
            "stage": "swarm_join",
            "detail": aggregation_result.summary,
            "status": "complete",
            "join_id": join_spec.join_id,
            "conflict_count": len(aggregation_result.conflicts),
            "degraded": aggregation_result.degraded,
        }
    )
    trace.append(
        {
            "stage": "compose_response",
            "detail": "research_module composed the Swarm research summary.",
            "status": "complete",
        }
    )
    return trace


def build_research_swarm_summary(
    *,
    branch_results: list[dict[str, Any]],
    aggregation_result: SwarmAggregationResult,
    degradation_decisions: list[SwarmDegradationDecision],
) -> str:
    business_output = build_research_swarm_business_output(
        branch_results=branch_results,
        aggregation_result=aggregation_result,
        degradation_decisions=degradation_decisions,
    )
    lines = [str(business_output["overall_summary"]["summary_text"]).strip()]
    for branch in list(business_output["per_branch_evidence"]):
        lines.append(f"- {branch['branch_label']}: {branch['branch_summary']}")
    notes = dict(business_output["conflict_and_degradation_notes"])
    if str(notes.get("conflict_summary") or "").strip():
        lines.append(str(notes["conflict_summary"]).strip())
    if str(notes.get("degradation_reason") or "").strip():
        lines.append(f"Degradation handling: {notes['degradation_reason']}")
    lines.append(f"Final merge decision: {notes['final_merge_decision']}")
    lines.append(f"Reliability note: {notes['reliability_note']}")
    return "\n".join(lines)


def build_research_swarm_business_output(
    *,
    branch_results: list[dict[str, Any]],
    aggregation_result: SwarmAggregationResult,
    degradation_decisions: list[SwarmDegradationDecision],
) -> dict[str, Any]:
    merged_branch_ids = {
        str(branch_id).strip()
        for item in aggregation_result.merged_items
        for branch_id in list(item.get("branch_ids") or [])
        if str(branch_id).strip()
    }
    per_branch_evidence: list[dict[str, Any]] = []
    degraded_branches: list[dict[str, Any]] = []
    failed_branch_count = 0
    degraded_branch_count = 0
    successful_branch_count = 0

    for result in branch_results:
        branch_id = str(result.get("branch_id") or "").strip()
        branch_label = str(result.get("branch_label") or result.get("input_ref") or branch_id or "branch").strip()
        branch_status = _branch_status(result)
        included_in_final_merge = bool(branch_id) and branch_id in merged_branch_ids
        not_included_reason = _not_included_reason(result=result, included_in_final_merge=included_in_final_merge)
        branch_summary = _branch_summary(
            result=result,
            branch_status=branch_status,
            included_in_final_merge=included_in_final_merge,
            not_included_reason=not_included_reason,
        )
        evidence_items = []
        for item in list(result.get("sources") or [])[:3]:
            evidence_items.append(
                {
                    "title": str(item.get("title") or item.get("url") or "Untitled source").strip(),
                    "url": str(item.get("url") or "").strip(),
                    "domain": str(item.get("domain") or "").strip(),
                }
            )
        record = {
            "branch_id": branch_id,
            "branch_label": branch_label,
            "branch_status": branch_status,
            "branch_summary": branch_summary,
            "branch_evidence_count": int(result.get("source_count") or 0),
            "included_in_final_merge": included_in_final_merge,
            "not_included_reason": not_included_reason,
            "result_grade": str(result.get("result_grade") or ""),
            "evidence_completeness": str(result.get("evidence_completeness") or ""),
            "branch_evidence": evidence_items,
        }
        per_branch_evidence.append(record)
        if branch_status == "failed":
            failed_branch_count += 1
        elif branch_status == "degraded":
            degraded_branch_count += 1
            degraded_branches.append(
                {
                    "branch_id": branch_id,
                    "branch_label": branch_label,
                    "degradation_reason": _degraded_branch_reason(result),
                }
            )
        else:
            successful_branch_count += 1

    conflict_detected = bool(aggregation_result.conflicts)
    conflict_summary = _conflict_summary(aggregation_result.conflicts)
    degradation_reason = (
        str(aggregation_result.degradation_reason).strip()
        if aggregation_result.degraded
        else "No branch required degradation handling."
    )
    final_merge_decision = _final_merge_decision(
        aggregation_result=aggregation_result,
        failed_branch_count=failed_branch_count,
    )
    reliability_note = _reliability_note(
        aggregation_result=aggregation_result,
        degraded_branch_count=degraded_branch_count,
        failed_branch_count=failed_branch_count,
    )
    overall_summary = {
        "summary_text": (
            f"Research swarm reviewed {len(branch_results)} branch(es), merged "
            f"{len(aggregation_result.merged_items)} final finding(s), and kept "
            f"{len(aggregation_result.conflicts)} conflict marker(s)."
        ),
        "branch_count": len(branch_results),
        "successful_branch_count": successful_branch_count,
        "degraded_branch_count": degraded_branch_count,
        "failed_branch_count": failed_branch_count,
        "merged_finding_count": len(aggregation_result.merged_items),
    }
    return {
        "overall_summary": overall_summary,
        "per_branch_evidence": per_branch_evidence,
        "conflict_and_degradation_notes": {
            "conflict_detected": conflict_detected,
            "conflict_summary": conflict_summary,
            "degraded_branches": degraded_branches,
            "degradation_reason": degradation_reason,
            "final_merge_decision": final_merge_decision,
            "reliability_note": reliability_note,
        },
    }


def _branch_status(result: dict[str, Any]) -> str:
    if not bool(result.get("ok")):
        return "failed"
    if bool(result.get("degraded")):
        return "degraded"
    grade = str(result.get("result_grade") or "").strip()
    if grade == "degraded":
        return "degraded"
    return "success"


def _not_included_reason(*, result: dict[str, Any], included_in_final_merge: bool) -> str:
    if included_in_final_merge:
        return ""
    if not bool(result.get("ok")):
        return "This branch failed and could not contribute evidence to the final merge."
    if int(result.get("source_count") or 0) <= 0:
        return "This branch returned no usable evidence."
    if not dict(result.get("top_source") or {}):
        return "This branch had evidence, but no top source was selected for the final merge."
    return "This branch did not contribute a distinct top source to the final merge."


def _branch_summary(
    *,
    result: dict[str, Any],
    branch_status: str,
    included_in_final_merge: bool,
    not_included_reason: str,
) -> str:
    source_count = int(result.get("source_count") or 0)
    top_source = dict(result.get("top_source") or {})
    top_title = str(top_source.get("title") or top_source.get("url") or "no top source").strip()
    if branch_status == "failed":
        return f"Failed to produce usable evidence. {not_included_reason}".strip()
    if branch_status == "degraded":
        if bool(result.get("degraded")):
            return (
                f"Recovered through serial replay, gathered {source_count} source(s), and "
                f"{'contributed to' if included_in_final_merge else 'did not contribute to'} the final merge. "
                f"Top evidence: {top_title}."
            )
        note = str(result.get("reliability_note") or "").strip()
        return (
            f"Produced {source_count} source(s) with degraded confidence. "
                f"Top evidence: {top_title}. {note}"
        ).strip()
    note = str(result.get("reliability_note") or "").strip()
    if str(result.get("result_grade") or "").strip() == "insufficient_evidence" and note:
        return (
            f"Produced {source_count} source(s) and contributed to the final merge, "
            f"but the evidence is not fully reliable. Top evidence: {top_title}. {note}"
        ).strip()
    return (
        f"Produced {source_count} source(s) and contributed to the final merge. "
        f"Top evidence: {top_title}."
    )


def _degraded_branch_reason(result: dict[str, Any]) -> str:
    if bool(result.get("degraded")):
        return "The branch failed during parallel execution and was recovered through serial replay."
    return str(result.get("reliability_note") or "The branch produced usable but incomplete evidence.").strip()


def _conflict_summary(conflicts: list[dict[str, Any]]) -> str:
    if not conflicts:
        return "No cross-branch conflict was detected in the final evidence set."
    titles = ", ".join(str(item.get("title") or "conflict").strip() for item in conflicts)
    return (
        f"Conflict detected across branch evidence for: {titles}. "
        "The system kept the conflicting evidence marked instead of forcing arbitration."
    )


def _final_merge_decision(
    *,
    aggregation_result: SwarmAggregationResult,
    failed_branch_count: int,
) -> str:
    if aggregation_result.conflicts and failed_branch_count:
        return "Merged usable branch evidence, kept conflict markers, and excluded failed branches from the final merge."
    if aggregation_result.conflicts:
        return "Merged usable branch evidence and kept conflict markers instead of forcing a single winner."
    if aggregation_result.degraded:
        return "Merged usable branch evidence after recovery handling for degraded branches."
    return "Merged branch evidence without conflict handling or degradation recovery."


def _reliability_note(
    *,
    aggregation_result: SwarmAggregationResult,
    degraded_branch_count: int,
    failed_branch_count: int,
) -> str:
    if failed_branch_count:
        return "The overall result is incomplete because at least one branch failed and could not be merged."
    if aggregation_result.conflicts:
        return "The overall result is usable, but some branch evidence conflicts and should be read with caution."
    if degraded_branch_count:
        return "The overall result is usable, but at least one branch needed degraded recovery handling."
    return "The overall result is supported by branch evidence with no marked conflicts."
