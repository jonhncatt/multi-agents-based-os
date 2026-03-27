from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path
import sys
from threading import Lock
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.bootstrap import AgentOSAssembleConfig, assemble_runtime
from app.config import load_config
from app.contracts import HealthReport, TaskRequest, ToolResult


@dataclass
class DemoResearchSwarmProvider:
    provider_id: str = "demo_research_swarm_provider"
    supported_tools: list[str] = field(default_factory=lambda: ["web.search", "web.fetch"])
    fail_once_queries: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        self._failed_once: set[str] = set()
        self._lock = Lock()

    def execute(self, call: Any) -> ToolResult:
        if call.name == "web.search":
            query = str(call.arguments.get("query") or "").strip()
            with self._lock:
                if query in self.fail_once_queries and query not in self._failed_once:
                    self._failed_once.add(query)
                    return ToolResult(
                        ok=False,
                        tool_name=call.name,
                        provider_id=self.provider_id,
                        error=f"simulated first-pass branch failure for {query}",
                    )
            return ToolResult(
                ok=True,
                tool_name=call.name,
                provider_id=self.provider_id,
                data={
                    "ok": True,
                    "query": query,
                    "results": self._results_for_query(query),
                },
            )
        if call.name == "web.fetch":
            url = str(call.arguments.get("url") or "")
            return ToolResult(
                ok=True,
                tool_name=call.name,
                provider_id=self.provider_id,
                data={
                    "ok": True,
                    "url": url,
                    "content": f"Fetched evidence body for {url}.",
                },
            )
        return ToolResult(ok=False, tool_name=call.name, provider_id=self.provider_id, error=f"unsupported tool: {call.name}")

    def health_check(self) -> HealthReport:
        return HealthReport(component_id=self.provider_id, status="healthy", summary="demo research swarm provider ready")

    def _results_for_query(self, query: str) -> list[dict[str, Any]]:
        slug = query.lower().replace(" ", "-")
        if query == "conflict alpha":
            return [
                {
                    "title": "Shared Research Conflict",
                    "url": "https://example.com/conflict-alpha",
                    "snippet": "Architecture branch source.",
                    "domain": "example.com",
                    "score": 9.8,
                    "source": "demo_swarm",
                }
            ]
        if query == "conflict beta":
            return [
                {
                    "title": "Shared Research Conflict",
                    "url": "https://example.com/conflict-beta",
                    "snippet": "Runtime branch source.",
                    "domain": "example.com",
                    "score": 9.5,
                    "source": "demo_swarm",
                }
            ]
        return [
            {
                "title": f"Research source for {query}",
                "url": f"https://example.com/{slug}",
                "snippet": f"Deterministic source preview for {query}.",
                "domain": "example.com",
                "score": 9.0,
                "source": "demo_swarm",
            }
        ]


def _bind_demo_provider(runtime: Any, *, fail_once_queries: set[str]) -> None:
    provider = DemoResearchSwarmProvider(fail_once_queries=fail_once_queries)
    runtime.kernel.register_provider(provider)
    for tool_name in ("web.search", "web.fetch"):
        contract = runtime.kernel.registry.get_tool_contract(tool_name)
        if contract is None:
            continue
        runtime.kernel.registry.register_tool_contract(
            contract,
            primary_provider=provider.provider_id,
            fallback_providers=[],
        )


def run_demo(*, check: bool) -> int:
    runtime = assemble_runtime(
        load_config(),
        assemble_config=AgentOSAssembleConfig(
            include_research_module=True,
            include_coding_module=False,
            include_adaptation_module=False,
            enable_session_provider=True,
        ),
    )
    fail_once_query = "branch failure note"
    _bind_demo_provider(runtime, fail_once_queries={fail_once_query})

    response = runtime.dispatch(
        TaskRequest(
            task_id="research-swarm-demo",
            task_type="task.research",
            message="run research swarm demo",
            context={
                "session_id": "research-swarm-demo-session",
                "execution_policy": "research_swarm_pipeline",
                "runtime_profile": "research_swarm_demo",
                "fetch_top_result": True,
                "swarm_mode": "parallel_research",
                "swarm_inputs": [
                    {"label": "Architecture brief", "query": "conflict alpha", "input_ref": "brief:architecture"},
                    {"label": "Runtime brief", "query": "conflict beta", "input_ref": "brief:runtime"},
                    {"label": "Failure brief", "query": fail_once_query, "input_ref": "brief:degradation"},
                ],
            },
        ),
        module_id="research_module",
    )

    trace = runtime.kernel.health_snapshot()["recent_traces"][-1]
    if check:
        assert response.ok is True
        assert response.payload["module_id"] == "research_module"
        assert response.payload["swarm"]["branch_count"] == 3
        assert response.payload["swarm"]["degradation"]["degraded"] is True
        assert len(response.payload["swarm"]["aggregation"]["conflicts"]) >= 1
        stages = [event["stage"] for event in trace["events"]]
        assert "swarm_branch_plan" in stages
        assert "swarm_degradation" in stages
        assert "swarm_join" in stages
        print("research swarm demo check passed")
        return 0

    print("Research Swarm MVP Demo")
    print("========================")
    print(response.text)
    print()
    print("Join summary:")
    print(response.payload["swarm"]["aggregation"]["summary"])
    print()
    print("Trace stages:")
    for event in trace["events"]:
        if event["stage"].startswith("swarm_"):
            print(f"- {event['stage']}: {event['detail']}")
    return 0 if response.ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the research swarm demo.")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    return run_demo(check=bool(args.check))


if __name__ == "__main__":
    raise SystemExit(main())
