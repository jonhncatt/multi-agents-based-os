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
    lines = [
        (
            f"Research swarm processed {len(branch_results)} input(s) and merged "
            f"{len(aggregation_result.merged_items)} unique finding(s)."
        )
    ]
    for result in branch_results:
        label = str(result.get("branch_label") or result.get("input_ref") or result.get("branch_id") or "branch").strip()
        top_source = dict(result.get("top_source") or {})
        top_title = str(top_source.get("title") or top_source.get("url") or "no top source").strip()
        attempt_mode = str(result.get("attempt_mode") or "parallel")
        status = "ok" if bool(result.get("ok")) else "failed"
        lines.append(
            f"- {label}: {status}, {int(result.get('source_count') or 0)} source(s), top source {top_title}, attempt={attempt_mode}."
        )
    if degradation_decisions:
        replayed = ", ".join(
            str(item.details.get("branch_id") or item.trigger).strip() or item.trigger for item in degradation_decisions
        )
        lines.append(f"Degradation handling: serial replay was triggered for {replayed}.")
    if aggregation_result.conflicts:
        conflict_titles = ", ".join(str(item.get("title") or "conflict").strip() for item in aggregation_result.conflicts)
        lines.append(f"Aggregator marked conflict(s) without forced arbitration: {conflict_titles}.")
    else:
        lines.append("Aggregator found no conflicting top-source titles across branches.")
    lines.append(aggregation_result.summary)
    return "\n".join(lines)
