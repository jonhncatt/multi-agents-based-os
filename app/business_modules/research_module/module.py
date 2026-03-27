from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from typing import Any

from app.business_modules.research_module.manifest import RESEARCH_MODULE_MANIFEST
from app.business_modules.research_module.pipeline.runtime import (
    aggregate_research_swarm_results,
    build_research_pipeline_trace,
    build_research_swarm_pipeline_trace,
    build_research_swarm_summary,
)
from app.business_modules.research_module.policies.catalog import RESEARCH_MODULE_POLICY_SET
from app.contracts import (
    HealthReport,
    SwarmBranchSpec,
    SwarmDegradationDecision,
    SwarmJoinSpec,
    TaskRequest,
    TaskResponse,
    ToolCall,
    ToolResult,
)
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

        swarm_inputs = self._normalize_swarm_inputs(request)
        if len(swarm_inputs) >= 2:
            return self._handle_swarm_request(request=request, context=context, tool_runtime=tool_runtime, swarm_inputs=swarm_inputs)
        return self._handle_single_request(request=request, context=context, tool_runtime=tool_runtime)

    def invoke(self, request: TaskRequest) -> TaskResponse:
        return self.handle(request, RuntimeContext(request_id=request.task_id, module_id=self.manifest.module_id))

    def _handle_single_request(self, *, request: TaskRequest, context: RuntimeContext, tool_runtime: Any) -> TaskResponse:
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
        result = self._execute_research_query(
            tool_runtime=tool_runtime,
            query=query,
            request_id=request.task_id,
            max_results=max_results,
            fetch_top=fetch_top,
            fetch_chars=fetch_chars,
            metadata={"source": "research_module"},
        )

        context.selected_roles = ["researcher"]
        context.selected_tools = list(result["selected_tools"])
        context.selected_providers = list(result["selected_providers"])
        context.execution_policy = context.execution_policy or "research_pipeline"
        context.runtime_profile = context.runtime_profile or "research"

        if not result["ok"]:
            context.health_state = "degraded"
            return TaskResponse(
                ok=False,
                task_id=request.task_id,
                error=result["error"] or "web.search failed",
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
                        "search": result["search"],
                        "sources": [],
                        "top_source": {},
                    },
                },
            )

        payload = {
            "module_id": self.manifest.module_id,
            "selected_roles": list(context.selected_roles),
            "selected_tools": list(context.selected_tools),
            "selected_providers": list(context.selected_providers),
            "policy_set": list(RESEARCH_MODULE_POLICY_SET),
            "module_pipeline": build_research_pipeline_trace(
                query=query,
                search_count=len(result["sources"]),
                fetch_attempted=bool(result["fetch_attempted"]),
                fetch_ok=bool(result["fetch_ok"]),
            ),
            "research": {
                "query": query,
                "source_count": len(result["sources"]),
                "sources": result["sources"],
                "top_source": result["top_source"],
                "search": result["search"],
                "fetch": result["fetch"],
            },
        }
        warnings = list(result["warnings"])
        return TaskResponse(
            ok=True,
            task_id=request.task_id,
            text=self._build_summary(query=query, sources=result["sources"], fetch_result=result["fetch_result"] if result["fetch_attempted"] else None),
            payload=payload,
            warnings=warnings,
        )

    def _handle_swarm_request(
        self,
        *,
        request: TaskRequest,
        context: RuntimeContext,
        tool_runtime: Any,
        swarm_inputs: list[dict[str, str]],
    ) -> TaskResponse:
        max_results = self._coerce_int(request.context.get("max_results"), 3, minimum=1, maximum=8)
        fetch_top = bool(request.context.get("fetch_top_result", True))
        fetch_chars = self._coerce_int(request.context.get("fetch_max_chars"), 2400, minimum=512, maximum=20000)
        max_workers = self._coerce_int(request.context.get("swarm_max_workers"), min(4, len(swarm_inputs)), minimum=1, maximum=6)
        swarm_run_id = f"{request.task_id}-swarm"
        branch_specs = [
            SwarmBranchSpec(
                branch_id=f"branch-{index + 1}",
                task_kind="research_branch",
                objective=item["query"],
                input_ref=item["input_ref"],
                runtime_profile="research_branch",
                required_tools=["web.search", "web.fetch"],
                metadata={"label": item["label"]},
            )
            for index, item in enumerate(swarm_inputs)
        ]
        join_spec = SwarmJoinSpec(join_id=f"{swarm_run_id}-join", branch_ids=[item.branch_id for item in branch_specs])

        context.selected_roles = ["researcher", "aggregator"]
        context.selected_tools = ["web.search", "web.fetch"]
        context.selected_providers = []
        context.execution_policy = context.execution_policy or "research_swarm_pipeline"
        context.runtime_profile = context.runtime_profile or "research_swarm"
        context.add_trace_event(
            stage="swarm_branch_plan",
            detail=f"research_module planned {len(branch_specs)} Swarm branches.",
            payload={
                "swarm_run_id": swarm_run_id,
                "branch_count": len(branch_specs),
                "join_id": join_spec.join_id,
            },
        )

        branch_results: list[dict[str, Any]] = []
        degradation_decisions: list[SwarmDegradationDecision] = []
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {
                pool.submit(
                    self._run_swarm_branch,
                    tool_runtime=tool_runtime,
                    spec=spec,
                    request_id=request.task_id,
                    max_results=max_results,
                    fetch_top=fetch_top,
                    fetch_chars=fetch_chars,
                    attempt_mode="parallel",
                ): spec
                for spec in branch_specs
            }
            for future in as_completed(futures):
                spec = futures[future]
                try:
                    branch_results.append(future.result())
                except Exception as exc:
                    branch_results.append(
                        {
                            "branch_id": spec.branch_id,
                            "branch_label": str(spec.metadata.get("label") or spec.input_ref),
                            "input_ref": spec.input_ref,
                            "query": spec.objective,
                            "ok": False,
                            "error": str(exc),
                            "source_count": 0,
                            "sources": [],
                            "top_source": {},
                            "warnings": ["parallel branch execution raised an unexpected error"],
                            "attempt_mode": "parallel",
                            "selected_providers": [],
                        }
                    )

        ordered_results = self._order_branch_results(branch_specs=branch_specs, branch_results=branch_results)
        final_results: list[dict[str, Any]] = []
        for result in ordered_results:
            if bool(result.get("ok")):
                final_results.append(result)
                continue
            branch_id = str(result.get("branch_id") or "")
            spec = next((item for item in branch_specs if item.branch_id == branch_id), None)
            if spec is None:
                final_results.append(result)
                continue
            decision = SwarmDegradationDecision(
                policy="serial_replay",
                trigger=f"branch_failed:{branch_id}",
                action="replay_failed_branch_sequentially",
                details={
                    "branch_id": branch_id,
                    "input_ref": spec.input_ref,
                    "initial_error": str(result.get("error") or "branch failed during parallel execution"),
                },
            )
            degradation_decisions.append(decision)
            replayed = self._run_swarm_branch(
                tool_runtime=tool_runtime,
                spec=spec,
                request_id=request.task_id,
                max_results=max_results,
                fetch_top=fetch_top,
                fetch_chars=fetch_chars,
                attempt_mode="serial_replay",
            )
            replayed["warnings"] = list(result.get("warnings") or []) + list(replayed.get("warnings") or [])
            replayed["degraded"] = True
            final_results.append(replayed)
            context.add_trace_event(
                stage="swarm_degradation",
                detail=f"serial_replay triggered for {branch_id}.",
                status="warning",
                payload=decision.to_dict(),
            )

        aggregation_result = aggregate_research_swarm_results(
            join_spec=join_spec,
            branch_results=final_results,
            degradation_decisions=degradation_decisions,
        )
        module_pipeline = build_research_swarm_pipeline_trace(
            swarm_run_id=swarm_run_id,
            branch_specs=branch_specs,
            branch_results=final_results,
            join_spec=join_spec,
            aggregation_result=aggregation_result,
            degradation_decisions=degradation_decisions,
        )
        for item in final_results:
            context.add_trace_event(
                stage="swarm_branch_result",
                detail=f"{item.get('branch_label')}: {item.get('source_count', 0)} source(s) gathered.",
                status="ok" if bool(item.get("ok")) else "error",
                payload={
                    "branch_id": item.get("branch_id"),
                    "input_ref": item.get("input_ref"),
                    "attempt_mode": item.get("attempt_mode"),
                    "source_count": item.get("source_count"),
                },
            )
        context.add_trace_event(
            stage="swarm_join",
            detail=aggregation_result.summary,
            payload={
                "join_id": join_spec.join_id,
                "conflict_count": len(aggregation_result.conflicts),
                "degraded": aggregation_result.degraded,
            },
        )

        selected_providers = sorted(
            {
                provider_id
                for item in final_results
                for provider_id in list(item.get("selected_providers") or [])
                if str(provider_id or "").strip()
            }
        )
        context.selected_providers = selected_providers
        warnings = [warning for item in final_results for warning in list(item.get("warnings") or [])]
        ok = all(bool(item.get("ok")) for item in final_results)
        if not ok:
            context.health_state = "degraded"
            warnings.append("research swarm finished with at least one failed branch")

        payload = {
            "module_id": self.manifest.module_id,
            "selected_roles": list(context.selected_roles),
            "selected_tools": list(context.selected_tools),
            "selected_providers": list(context.selected_providers),
            "policy_set": list(RESEARCH_MODULE_POLICY_SET),
            "module_pipeline": module_pipeline,
            "swarm": {
                "swarm_run_id": swarm_run_id,
                "branch_count": len(branch_specs),
                "max_workers": max_workers,
                "branch_specs": [item.to_dict() for item in branch_specs],
                "join_spec": join_spec.to_dict(),
                "branches": final_results,
                "aggregation": aggregation_result.to_dict(),
                "degradation": {
                    "degraded": bool(degradation_decisions),
                    "decisions": [item.to_dict() for item in degradation_decisions],
                },
            },
        }
        return TaskResponse(
            ok=ok,
            task_id=request.task_id,
            text=build_research_swarm_summary(
                branch_results=final_results,
                aggregation_result=aggregation_result,
                degradation_decisions=degradation_decisions,
            ),
            payload=payload,
            warnings=warnings,
            error="" if ok else "research swarm failed after serial replay",
        )

    def _run_swarm_branch(
        self,
        *,
        tool_runtime: Any,
        spec: SwarmBranchSpec,
        request_id: str,
        max_results: int,
        fetch_top: bool,
        fetch_chars: int,
        attempt_mode: str,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        result = self._execute_research_query(
            tool_runtime=tool_runtime,
            query=spec.objective,
            request_id=request_id,
            max_results=max_results,
            fetch_top=fetch_top,
            fetch_chars=fetch_chars,
            disable_contract_retries=True,
            metadata={
                "source": "research_module.swarm",
                "swarm_branch_id": spec.branch_id,
                "swarm_input_ref": spec.input_ref,
                "attempt_mode": attempt_mode,
            },
        )
        payload = {
            "branch_id": spec.branch_id,
            "branch_label": str(spec.metadata.get("label") or spec.input_ref),
            "input_ref": spec.input_ref,
            "query": spec.objective,
            "ok": bool(result["ok"]),
            "error": str(result["error"] or ""),
            "source_count": len(result["sources"]),
            "sources": result["sources"],
            "top_source": result["top_source"],
            "search": result["search"],
            "fetch": result["fetch"],
            "warnings": list(result["warnings"]),
            "attempt_mode": attempt_mode,
            "selected_tools": list(result["selected_tools"]),
            "selected_providers": list(result["selected_providers"]),
            "elapsed_ms": max(0, int((time.perf_counter() - started) * 1000)),
        }
        return payload

    def _execute_research_query(
        self,
        *,
        tool_runtime: Any,
        query: str,
        request_id: str,
        max_results: int,
        fetch_top: bool,
        fetch_chars: int,
        disable_contract_retries: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        call_metadata = {"request_id": request_id}
        call_metadata.update(dict(metadata or {}))
        search_call = ToolCall(
            name="web.search",
            arguments={"query": query, "max_results": max_results},
            timeout_sec=10.0,
            retries=-1 if disable_contract_retries else 0,
            metadata=call_metadata,
        )
        search_result = self._coerce_tool_result(tool_runtime.execute(search_call), fallback_name=search_call.name)
        selected_tools = [search_call.name]
        selected_providers = [search_result.provider_id] if search_result.provider_id else []
        if not search_result.ok:
            return {
                "ok": False,
                "error": search_result.error or "web.search failed",
                "warnings": ["search branch failed before aggregation"],
                "search": search_result.to_dict(),
                "fetch": {},
                "fetch_result": None,
                "fetch_attempted": False,
                "fetch_ok": False,
                "sources": [],
                "top_source": {},
                "selected_tools": selected_tools,
                "selected_providers": selected_providers,
            }

        sources = self._normalize_sources(search_result)
        top_source = dict(sources[0]) if sources else {}
        fetch_attempted = False
        fetch_result: ToolResult | None = None
        warnings: list[str] = []
        if fetch_top and str(top_source.get("url") or "").strip():
            fetch_attempted = True
            fetch_call = ToolCall(
                name="web.fetch",
                arguments={"url": str(top_source.get("url") or ""), "max_chars": fetch_chars},
                timeout_sec=12.0,
                retries=-1 if disable_contract_retries else 0,
                metadata=call_metadata,
            )
            fetch_result = self._coerce_tool_result(tool_runtime.execute(fetch_call), fallback_name=fetch_call.name)
            selected_tools.append(fetch_call.name)
            if fetch_result.provider_id and fetch_result.provider_id not in selected_providers:
                selected_providers.append(fetch_result.provider_id)
            if not fetch_result.ok:
                warnings.append("top source fetch failed; branch returned search-only evidence")

        return {
            "ok": True,
            "error": "",
            "warnings": warnings,
            "search": search_result.to_dict(),
            "fetch": fetch_result.to_dict() if fetch_result is not None else {},
            "fetch_result": fetch_result,
            "fetch_attempted": fetch_attempted,
            "fetch_ok": bool(fetch_result.ok) if fetch_result is not None else False,
            "sources": sources,
            "top_source": top_source,
            "selected_tools": selected_tools,
            "selected_providers": selected_providers,
        }

    def _normalize_swarm_inputs(self, request: TaskRequest) -> list[dict[str, str]]:
        raw = request.context.get("swarm_inputs")
        if not isinstance(raw, list):
            return []
        normalized: list[dict[str, str]] = []
        for index, item in enumerate(raw, start=1):
            if isinstance(item, str):
                query = str(item).strip()
                if not query:
                    continue
                normalized.append(
                    {
                        "label": f"Input {index}",
                        "query": query,
                        "input_ref": f"input:{index}",
                    }
                )
                continue
            if not isinstance(item, dict):
                continue
            query = str(item.get("query") or item.get("message") or item.get("objective") or item.get("topic") or "").strip()
            if not query:
                continue
            label = str(item.get("label") or item.get("name") or f"Input {index}").strip() or f"Input {index}"
            input_ref = str(item.get("input_ref") or item.get("document_id") or item.get("attachment_id") or f"input:{index}").strip() or f"input:{index}"
            normalized.append(
                {
                    "label": label,
                    "query": query,
                    "input_ref": input_ref,
                }
            )
        return normalized

    def _order_branch_results(
        self,
        *,
        branch_specs: list[SwarmBranchSpec],
        branch_results: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        result_index = {str(item.get("branch_id") or ""): item for item in branch_results}
        return [result_index.get(spec.branch_id, {"branch_id": spec.branch_id, "ok": False, "error": "missing branch result"}) for spec in branch_specs]

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
