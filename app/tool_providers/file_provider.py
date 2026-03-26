from __future__ import annotations

from typing import Any

from app.config import AppConfig
from app.contracts import BaseToolProvider, HealthReport, ToolCall, ToolResult
from app.local_tools import LocalToolExecutor


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


class LocalFileProvider(BaseToolProvider):
    provider_id = "local_file_provider"
    supported_tools = ["file.read", "code.search"]

    def __init__(self, config: AppConfig, *, executor: LocalToolExecutor | None = None) -> None:
        self._executor = executor or LocalToolExecutor(config)

    def execute(self, call: ToolCall) -> ToolResult:
        tool_name = str(call.name or "").strip()
        if tool_name not in {"file.read", "code.search"}:
            return ToolResult(
                ok=False,
                tool_name=call.name,
                provider_id=self.provider_id,
                error=f"unsupported tool: {call.name}",
            )

        args = dict(call.arguments or {})
        operation = str(args.get("operation") or ("code_search" if tool_name == "code.search" else "read")).strip().lower()
        legacy_name = "read_text_file"
        legacy_args: dict[str, Any]

        if operation == "read":
            legacy_args = {
                "path": str(args.get("path") or ""),
                "start_char": max(0, _coerce_int(args.get("start_char"), 0)),
                "max_chars": max(128, _coerce_int(args.get("max_chars"), 200000)),
                "start_line": max(0, _coerce_int(args.get("start_line"), 0)),
                "max_lines": max(0, _coerce_int(args.get("max_lines"), 0)),
            }
        elif operation == "search":
            legacy_name = "search_text_in_file"
            legacy_args = {
                "path": str(args.get("path") or ""),
                "query": str(args.get("query") or ""),
                "max_matches": max(1, _coerce_int(args.get("max_matches"), 8)),
                "context_chars": max(40, _coerce_int(args.get("context_chars"), 280)),
            }
        elif operation == "multi_search":
            legacy_name = "multi_query_search"
            queries = args.get("queries")
            legacy_args = {
                "path": str(args.get("path") or ""),
                "queries": queries if isinstance(queries, list) else [],
                "per_query_max_matches": max(1, _coerce_int(args.get("per_query_max_matches"), 3)),
                "context_chars": max(40, _coerce_int(args.get("context_chars"), 280)),
            }
        elif operation == "heading":
            legacy_name = "read_section_by_heading"
            legacy_args = {
                "path": str(args.get("path") or ""),
                "heading": str(args.get("heading") or ""),
                "max_chars": max(512, _coerce_int(args.get("max_chars"), 12000)),
            }
        elif operation == "table":
            legacy_name = "table_extract"
            legacy_args = {
                "path": str(args.get("path") or ""),
                "query": str(args.get("query") or ""),
                "page_hint": max(0, _coerce_int(args.get("page_hint"), 0)),
                "max_tables": max(1, _coerce_int(args.get("max_tables"), 5)),
                "max_rows": max(1, _coerce_int(args.get("max_rows"), 25)),
            }
        elif operation == "fact_check":
            legacy_name = "fact_check_file"
            queries = args.get("queries")
            legacy_args = {
                "path": str(args.get("path") or ""),
                "claim": str(args.get("claim") or ""),
                "queries": queries if isinstance(queries, list) else [],
                "max_evidence": max(1, _coerce_int(args.get("max_evidence"), 6)),
            }
        elif operation == "code_search":
            legacy_name = "search_codebase"
            legacy_args = {
                "query": str(args.get("query") or ""),
                "root": str(args.get("root") or "."),
                "max_matches": max(1, _coerce_int(args.get("max_matches"), 20)),
                "file_glob": str(args.get("file_glob") or ""),
                "use_regex": bool(args.get("use_regex", False)),
                "case_sensitive": bool(args.get("case_sensitive", False)),
            }
        else:
            return ToolResult(
                ok=False,
                tool_name=call.name,
                provider_id=self.provider_id,
                error=f"unsupported file.read operation: {operation}",
            )

        payload = self._executor.execute(legacy_name, legacy_args)
        return ToolResult(
            ok=bool(payload.get("ok")),
            tool_name=tool_name,
            provider_id=self.provider_id,
            data=payload,
            error=str(payload.get("error") or ""),
        )

    def health_check(self) -> HealthReport:
        return HealthReport(
            component_id=self.provider_id,
            status="healthy",
            summary="file provider active",
            details={"supported_tools": list(self.supported_tools)},
        )
