from __future__ import annotations

from typing import Any


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
