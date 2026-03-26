from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import replace
from typing import Any

from app.contracts import ProviderUnavailableError, ToolCall, ToolExecutionError, ToolResult
from app.contracts.module import BaseToolProvider
from app.kernel.event_bus import EventBus
from app.kernel.registry import ModuleRegistry


class ToolBus:
    def __init__(self, registry: ModuleRegistry, *, event_bus: EventBus | None = None) -> None:
        self.registry = registry
        self.event_bus = event_bus

    def register_provider(self, provider: BaseToolProvider) -> None:
        self.registry.register_provider(provider)

    def execute(self, call: ToolCall) -> ToolResult:
        normalized_call = replace(call, name=str(call.name or "").strip())
        if not normalized_call.name:
            return ToolResult(ok=False, tool_name="", provider_id="", error="tool name is required", attempts=1)

        contract = self.registry.get_tool_contract(normalized_call.name)
        timeout = float(normalized_call.timeout_sec) if normalized_call.timeout_sec is not None else float(getattr(contract, "timeout", 0.0) or 0.0)
        retries = max(0, int(normalized_call.retries) if normalized_call.retries else int((getattr(contract, "retry_policy", {}) or {}).get("max_retries", 0) or 0))
        prepared_call = replace(normalized_call, timeout_sec=timeout, retries=retries)

        providers = self.registry.providers_for_tool(prepared_call.name)
        if not providers:
            return ToolResult(
                ok=False,
                tool_name=prepared_call.name,
                provider_id="",
                error=f"no provider registered for tool: {prepared_call.name}",
                attempts=1,
            )

        primary_result = self._execute_provider_chain(prepared_call, providers)
        if primary_result.ok:
            return primary_result

        fallback_tools = [str(item or "").strip() for item in prepared_call.fallback_tools if str(item or "").strip()]
        last_result = primary_result
        for fallback_name in fallback_tools:
            fallback_providers = self.registry.providers_for_tool(fallback_name)
            if not fallback_providers:
                continue
            fallback_call = replace(
                prepared_call,
                name=fallback_name,
                fallback_tools=[],
                metadata={**dict(prepared_call.metadata), "fallback_for": prepared_call.name},
            )
            fallback_result = self._execute_provider_chain(fallback_call, fallback_providers, mark_fallback=True)
            last_result = fallback_result
            if fallback_result.ok:
                return fallback_result
        return last_result

    def _execute_provider_chain(
        self,
        call: ToolCall,
        providers: list[BaseToolProvider],
        *,
        mark_fallback: bool = False,
    ) -> ToolResult:
        last_result = ToolResult(ok=False, tool_name=call.name, provider_id="", error="tool execution did not start", attempts=1)
        for index, provider in enumerate(providers):
            result = self._execute_with_retries(provider, call)
            if result.ok:
                if mark_fallback or index > 0:
                    result.fallback_used = True
                    self._publish(
                        "tool_fallback",
                        {
                            "tool": call.name,
                            "provider_id": provider.provider_id,
                            "fallback_used": True,
                        },
                    )
                return result
            last_result = result
        return last_result

    def _execute_with_retries(self, provider: BaseToolProvider, call: ToolCall) -> ToolResult:
        attempts = max(1, int(call.retries) + 1)
        last_result = ToolResult(ok=False, tool_name=call.name, provider_id=provider.provider_id, error="tool execution did not start", attempts=1)
        for attempt in range(1, attempts + 1):
            result = self._execute_once(provider, call, attempt=attempt)
            last_result = result
            if result.ok:
                return result
        return last_result

    def _execute_once(self, provider: BaseToolProvider, call: ToolCall, *, attempt: int) -> ToolResult:
        timeout = float(call.timeout_sec) if call.timeout_sec else 0.0
        timeout = max(0.0, timeout)
        provider_state = self.registry.providers.state(provider.provider_id)
        if provider_state.status == "disabled" or provider_state.circuit_open:
            message = f"provider unavailable: {provider.provider_id}"
            self._publish(
                "provider_skipped",
                {"provider_id": provider.provider_id, "tool": call.name, "reason": message},
            )
            return ToolResult(ok=False, tool_name=call.name, provider_id=provider.provider_id, error=message, attempts=attempt)

        self._publish(
            "tool_dispatch",
            {"tool": call.name, "provider_id": provider.provider_id, "attempt": attempt},
        )

        try:
            if timeout > 0:
                with ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(provider.execute, call)
                    raw_result = future.result(timeout=timeout)
            else:
                raw_result = provider.execute(call)
        except TimeoutError:
            state = self.registry.providers.record_failure(provider.provider_id, f"timeout after {timeout:.2f}s")
            self._publish("provider_failed", {"provider_id": provider.provider_id, "tool": call.name, "error": state.last_error})
            if state.circuit_open:
                self._publish("provider_circuit_open", {"provider_id": provider.provider_id, "tool": call.name})
            return ToolResult(ok=False, tool_name=call.name, provider_id=provider.provider_id, error=state.last_error, attempts=attempt)
        except ProviderUnavailableError as exc:
            state = self.registry.providers.record_failure(provider.provider_id, str(exc))
            self._publish("provider_failed", {"provider_id": provider.provider_id, "tool": call.name, "error": state.last_error})
            if state.circuit_open:
                self._publish("provider_circuit_open", {"provider_id": provider.provider_id, "tool": call.name})
            return ToolResult(ok=False, tool_name=call.name, provider_id=provider.provider_id, error=str(exc), attempts=attempt)
        except Exception as exc:
            state = self.registry.providers.record_failure(provider.provider_id, f"provider execution failed: {exc}")
            self._publish("provider_failed", {"provider_id": provider.provider_id, "tool": call.name, "error": state.last_error})
            if state.circuit_open:
                self._publish("provider_circuit_open", {"provider_id": provider.provider_id, "tool": call.name})
            return ToolResult(ok=False, tool_name=call.name, provider_id=provider.provider_id, error=state.last_error, attempts=attempt)

        result = self._coerce_result(raw_result, call=call, provider=provider, attempt=attempt)
        if result.ok:
            self.registry.providers.record_success(provider.provider_id)
        else:
            self.registry.providers.record_failure(provider.provider_id, result.error)
        self._publish(
            "tool_result",
            {
                "tool": result.tool_name,
                "provider_id": result.provider_id,
                "ok": result.ok,
                "attempt": result.attempts,
            },
        )
        return result

    def _coerce_result(self, raw_result: Any, *, call: ToolCall, provider: BaseToolProvider, attempt: int) -> ToolResult:
        if isinstance(raw_result, ToolResult):
            raw_result.attempts = attempt
            if not raw_result.tool_name:
                raw_result.tool_name = call.name
            if not raw_result.provider_id:
                raw_result.provider_id = provider.provider_id
            return raw_result
        if isinstance(raw_result, dict):
            return ToolResult(
                ok=bool(raw_result.get("ok")),
                tool_name=call.name,
                provider_id=str(raw_result.get("provider_id") or provider.provider_id),
                data=dict(raw_result),
                error=str(raw_result.get("error") or ""),
                attempts=attempt,
            )
        return ToolResult(
            ok=False,
            tool_name=call.name,
            provider_id=provider.provider_id,
            error="provider returned unsupported result type",
            attempts=attempt,
        )

    def _publish(self, event: str, payload: dict[str, Any]) -> None:
        if self.event_bus is None:
            return
        self.event_bus.publish(event, payload)

    def execute_or_raise(self, call: ToolCall) -> ToolResult:
        result = self.execute(call)
        if result.ok:
            return result
        raise ToolExecutionError(result.error or f"tool execution failed: {call.name}")
