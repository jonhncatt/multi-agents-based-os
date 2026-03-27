from __future__ import annotations

from typing import Any

from app.business_modules.research_module.manifest import RESEARCH_MODULE_MANIFEST
from app.business_modules.research_module.pipeline.runtime import build_research_pipeline_trace
from app.business_modules.research_module.policies.catalog import RESEARCH_MODULE_POLICY_SET
from app.contracts import HealthReport, TaskRequest, TaskResponse, ToolCall, ToolResult
from app.kernel.runtime_context import RuntimeContext


class ResearchModule:
    manifest = RESEARCH_MODULE_MANIFEST

    def __init__(self) -> None:
        self._kernel_context: Any = None

    def init(self, kernel_context: Any) -> None:
        self._kernel_context = kernel_context

    def health_check(self) -> HealthReport:
        ready = self._kernel_context is not None
        return HealthReport(
            component_id=self.manifest.module_id,
            status="healthy" if ready else "degraded",
            summary="research module ready" if ready else "research module waiting for kernel init",
            details={
                "required_tools": list(self.manifest.required_tools),
                "optional_tools": list(self.manifest.optional_tools),
                "policy_set": list(RESEARCH_MODULE_POLICY_SET),
            },
        )

    def shutdown(self) -> None:
        return None

    def handle(self, request: TaskRequest, context: RuntimeContext) -> TaskResponse:
        tool_runtime = self._kernel_context.lookup_module("tool_runtime_module") if self._kernel_context is not None else None
        if tool_runtime is None or not hasattr(tool_runtime, "execute"):
            context.health_state = "degraded"
            return TaskResponse(
                ok=False,
                task_id=request.task_id,
                error="tool_runtime_module is unavailable",
                warnings=["research_module could not resolve the tool runtime module"],
                payload={"module_id": self.manifest.module_id},
            )

        query = str(request.context.get("research_query") or request.message or "").strip()
        if not query:
            return TaskResponse(
                ok=False,
                task_id=request.task_id,
                error="research query is required",
                warnings=["research_module requires a non-empty query"],
                payload={"module_id": self.manifest.module_id},
            )

        max_results = self._coerce_int(request.context.get("max_results"), 3, minimum=1, maximum=8)
        fetch_top = bool(request.context.get("fetch_top_result", True))
        fetch_chars = self._coerce_int(request.context.get("fetch_max_chars"), 2400, minimum=512, maximum=20000)

        search_call = ToolCall(
            name="web.search",
            arguments={"query": query, "max_results": max_results},
            timeout_sec=10.0,
            metadata={"source": "research_module", "request_id": request.task_id},
        )
        search_result = self._coerce_tool_result(tool_runtime.execute(search_call), fallback_name=search_call.name)

        context.selected_roles = ["researcher"]
        context.selected_tools = [search_call.name]
        context.selected_providers = [search_result.provider_id] if search_result.provider_id else []
        context.execution_policy = context.execution_policy or "research_pipeline"
        context.runtime_profile = context.runtime_profile or "research"

        if not search_result.ok:
            context.health_state = "degraded"
            return TaskResponse(
                ok=False,
                task_id=request.task_id,
                error=search_result.error or "web.search failed",
                warnings=["research_module could not gather sources"],
                payload={
                    "module_id": self.manifest.module_id,
                    "selected_roles": list(context.selected_roles),
                    "selected_tools": list(context.selected_tools),
                    "selected_providers": list(context.selected_providers),
                    "policy_set": list(RESEARCH_MODULE_POLICY_SET),
                    "module_pipeline": build_research_pipeline_trace(
                        query=query,
                        search_count=0,
                        fetch_attempted=False,
                        fetch_ok=False,
                    ),
                    "research": {
                        "query": query,
                        "search": search_result.to_dict(),
                        "sources": [],
                        "top_source": {},
                    },
                },
            )

        sources = self._normalize_sources(search_result)
        top_source = dict(sources[0]) if sources else {}

        fetch_result = ToolResult(ok=False, tool_name="web.fetch", provider_id="", error="")
        fetch_attempted = False
        if fetch_top and str(top_source.get("url") or "").strip():
            fetch_attempted = True
            fetch_call = ToolCall(
                name="web.fetch",
                arguments={"url": str(top_source.get("url") or ""), "max_chars": fetch_chars},
                timeout_sec=12.0,
                metadata={"source": "research_module", "request_id": request.task_id},
            )
            fetch_result = self._coerce_tool_result(tool_runtime.execute(fetch_call), fallback_name=fetch_call.name)
            context.selected_tools.append(fetch_call.name)
            if fetch_result.provider_id and fetch_result.provider_id not in context.selected_providers:
                context.selected_providers.append(fetch_result.provider_id)

        summary = self._build_summary(query=query, sources=sources, fetch_result=fetch_result if fetch_attempted else None)
        payload = {
            "module_id": self.manifest.module_id,
            "selected_roles": list(context.selected_roles),
            "selected_tools": list(context.selected_tools),
            "selected_providers": list(context.selected_providers),
            "policy_set": list(RESEARCH_MODULE_POLICY_SET),
            "module_pipeline": build_research_pipeline_trace(
                query=query,
                search_count=len(sources),
                fetch_attempted=fetch_attempted,
                fetch_ok=bool(fetch_result.ok),
            ),
            "research": {
                "query": query,
                "source_count": len(sources),
                "sources": sources,
                "top_source": top_source,
                "search": search_result.to_dict(),
                "fetch": fetch_result.to_dict() if fetch_attempted else {},
            },
        }
        warnings: list[str] = []
        if fetch_attempted and not fetch_result.ok:
            warnings.append("top source fetch failed; returning search-only research summary")
        return TaskResponse(
            ok=True,
            task_id=request.task_id,
            text=summary,
            payload=payload,
            warnings=warnings,
        )

    def invoke(self, request: TaskRequest) -> TaskResponse:
        return self.handle(request, RuntimeContext(request_id=request.task_id, module_id=self.manifest.module_id))

    def _normalize_sources(self, result: ToolResult) -> list[dict[str, Any]]:
        raw = result.data.get("results") or result.data.get("data", {}).get("results") or []
        sources: list[dict[str, Any]] = []
        for item in list(raw):
            if not isinstance(item, dict):
                continue
            sources.append(
                {
                    "title": str(item.get("title") or "").strip(),
                    "url": str(item.get("url") or "").strip(),
                    "snippet": str(item.get("snippet") or "").strip(),
                    "domain": str(item.get("domain") or "").strip(),
                    "score": item.get("score"),
                    "source": str(item.get("source") or "").strip(),
                }
            )
        return sources

    def _build_summary(
        self,
        *,
        query: str,
        sources: list[dict[str, Any]],
        fetch_result: ToolResult | None,
    ) -> str:
        if not sources:
            return f"Research module found no usable sources for query: {query}"

        top = sources[0]
        source_count = len(sources)
        top_title = str(top.get("title") or top.get("url") or "top source").strip()
        top_domain = str(top.get("domain") or "").strip()
        top_snippet = str(top.get("snippet") or "").strip()
        lines = [
            f"Research module gathered {source_count} source(s) for '{query}'.",
            f"Top source: {top_title}" + (f" ({top_domain})" if top_domain else ""),
        ]
        if top_snippet:
            lines.append(f"Search preview: {top_snippet[:240]}")
        if fetch_result is not None and fetch_result.ok:
            fetched = str(fetch_result.data.get("content") or fetch_result.data.get("data", {}).get("content") or "").strip()
            if fetched:
                compact = " ".join(fetched.split())
                lines.append(f"Fetched evidence: {compact[:320]}")
        return " ".join(part for part in lines if part)

    def _coerce_tool_result(self, value: Any, *, fallback_name: str) -> ToolResult:
        if isinstance(value, ToolResult):
            return value
        if isinstance(value, dict):
            return ToolResult(
                ok=bool(value.get("ok")),
                tool_name=fallback_name,
                provider_id=str(value.get("provider_id") or ""),
                data=dict(value),
                error=str(value.get("error") or ""),
            )
        return ToolResult(
            ok=False,
            tool_name=fallback_name,
            provider_id="",
            error="tool runtime returned an invalid result",
        )

    def _coerce_int(self, value: Any, default: int, *, minimum: int, maximum: int) -> int:
        try:
            parsed = int(value)
        except Exception:
            parsed = default
        return max(minimum, min(maximum, parsed))
