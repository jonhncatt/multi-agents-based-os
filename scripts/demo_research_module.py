from __future__ import annotations

import argparse
from dataclasses import dataclass
import sys
from typing import Any
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.bootstrap import AgentOSAssembleConfig, assemble_runtime
from app.config import load_config
from app.contracts import HealthReport, TaskRequest, ToolResult


@dataclass
class DemoResearchProvider:
    provider_id: str = "demo_research_provider"
    supported_tools: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self.supported_tools = ["web.search", "web.fetch"]

    def execute(self, call: Any) -> ToolResult:
        if call.name == "web.search":
            return ToolResult(
                ok=True,
                tool_name=call.name,
                provider_id=self.provider_id,
                data={
                    "ok": True,
                    "query": call.arguments.get("query"),
                    "results": [
                        {
                            "title": "Agent OS overview",
                            "url": "https://example.com/agent-os",
                            "snippet": "A deterministic research demo source.",
                            "domain": "example.com",
                            "score": 9.9,
                            "source": "demo_provider",
                        }
                    ],
                },
            )
        if call.name == "web.fetch":
            return ToolResult(
                ok=True,
                tool_name=call.name,
                provider_id=self.provider_id,
                data={
                    "ok": True,
                    "url": call.arguments.get("url"),
                    "content": "Agent OS separates kernel, modules, and providers into explicit layers.",
                },
            )
        return ToolResult(ok=False, tool_name=call.name, provider_id=self.provider_id, error=f"unsupported tool: {call.name}")

    def health_check(self) -> HealthReport:
        return HealthReport(component_id=self.provider_id, status="healthy", summary="demo research provider ready")


def _bind_demo_provider(runtime: Any) -> None:
    provider = DemoResearchProvider()
    runtime.kernel.register_provider(provider)
    for tool_name in ("web.search", "web.fetch"):
        contract = runtime.kernel.registry.get_tool_contract(tool_name)
        if contract is None:
            continue
        fallback = ["http_web_provider"] if tool_name in {"web.search", "web.fetch"} else []
        runtime.kernel.registry.register_tool_contract(contract, primary_provider=provider.provider_id, fallback_providers=fallback)


def run_demo(*, query: str, check: bool) -> int:
    runtime = assemble_runtime(
        load_config(),
        assemble_config=AgentOSAssembleConfig(
            include_research_module=True,
            include_coding_module=False,
            include_adaptation_module=False,
            enable_session_provider=True,
        ),
    )
    _bind_demo_provider(runtime)
    response = runtime.dispatch(
        TaskRequest(
            task_id="research-demo",
            task_type="task.research",
            message=query,
            context={
                "session_id": "research-demo-session",
                "fetch_top_result": True,
                "runtime_profile": "research_demo",
                "execution_policy": "research_pipeline",
            },
        ),
        module_id="research_module",
    )
    if check:
        assert response.ok is True
        assert response.payload["module_id"] == "research_module"
        assert response.payload["research"]["source_count"] >= 1
        print("research module demo check passed")
        return 0

    print(response.text)
    return 0 if response.ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the research module demo.")
    parser.add_argument("--query", default="agent os separation of concerns")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    return run_demo(query=args.query, check=bool(args.check))


if __name__ == "__main__":
    raise SystemExit(main())
