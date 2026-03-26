from __future__ import annotations

from typing import Any

from app.intent_classifier import IntentClassifier
from app.policy_router import PolicyRouter
from app.route_trace import build_route_trace
from app.route_verifier import RouteVerifier
from app.router_signals import RouterSignalExtractor


class StubSettings:
    def __init__(self, *, enable_tools: bool = True) -> None:
        self.enable_tools = enable_tools


class StubAuthManager:
    def auth_summary(self) -> dict[str, Any]:
        return {"available": False, "reason": "stub_no_llm"}


class StubAgent:
    def __init__(self) -> None:
        self._auth_manager = StubAuthManager()

    def _looks_like_context_dependent_followup(self, text: str) -> bool:
        lowered = str(text or "").strip().lower()
        markers = ("继续", "刚才", "改成", "翻成", "再", "按刚才", "continue", "rewrite", "shorter")
        return any(marker in lowered for marker in markers)

    def _looks_like_spec_lookup_request(self, user_message: str, attachment_metas: list[dict[str, Any]]) -> bool:
        _ = attachment_metas
        return "spec" in str(user_message or "").lower()

    def _requires_evidence_mode(self, user_message: str, attachment_metas: list[dict[str, Any]]) -> bool:
        _ = attachment_metas
        lowered = str(user_message or "").lower()
        return any(marker in lowered for marker in ("证据", "出处", "来源", "依据", "source", "evidence"))

    def _attachment_needs_tooling(self, meta: dict[str, Any]) -> bool:
        return bool(meta.get("needs_tooling"))

    def _attachment_is_inline_parseable(self, meta: dict[str, Any]) -> bool:
        return bool(meta.get("inline_parseable", not bool(meta.get("needs_tooling"))))

    def _looks_like_inline_document_payload(self, user_message: str) -> bool:
        return "```" in str(user_message or "")

    def _looks_like_understanding_request(self, user_message: str) -> bool:
        lowered = str(user_message or "").lower()
        return any(marker in lowered for marker in ("解释", "说明", "总结", "整体", "explain", "summarize"))

    def _looks_like_holistic_document_explanation_request(self, user_message: str) -> bool:
        lowered = str(user_message or "").lower()
        return any(marker in lowered for marker in ("整体", "全文", "full doc"))

    def _looks_like_source_trace_request(self, user_message: str) -> bool:
        lowered = str(user_message or "").lower()
        return any(marker in lowered for marker in ("出处", "来源", "依据", "source", "evidence"))

    def _looks_like_explicit_tool_confirmation(self, user_message: str) -> bool:
        return str(user_message or "").strip().lower() in {"继续", "执行", "可以", "continue", "go ahead"}

    def _looks_like_meeting_minutes_request(self, user_message: str) -> bool:
        lowered = str(user_message or "").lower()
        return "会议纪要" in lowered or "meeting minutes" in lowered

    def _looks_like_internal_ticket_reference(self, user_message: str) -> bool:
        return "jira" in str(user_message or "").lower()

    def _request_likely_requires_tools(self, user_message: str, attachment_metas: list[dict[str, Any]]) -> bool:
        if attachment_metas:
            return True
        lowered = str(user_message or "").lower()
        markers = (
            "查",
            "定位",
            "repo",
            "函数",
            "新闻",
            "today",
            "web",
            "修改",
            "修复",
            "代码",
            "find",
            "lookup",
        )
        return any(marker in lowered for marker in markers)

    def _looks_like_local_code_lookup_request(self, user_message: str, attachment_metas: list[dict[str, Any]]) -> bool:
        _ = attachment_metas
        lowered = str(user_message or "").lower()
        return any(marker in lowered for marker in ("函数", "repo", "代码", "function", "file"))

    def _message_has_explicit_local_path(self, user_message: str) -> bool:
        lowered = str(user_message or "").lower()
        return ("/" in lowered) and ("." in lowered)

    def _has_file_like_lookup_token(self, text: str) -> bool:
        lowered = str(text or "").lower()
        return any(token in lowered for token in (".py", ".ts", ".md", ".json", "repo"))

    def _should_auto_search_default_roots(self, user_message: str, attachment_metas: list[dict[str, Any]]) -> bool:
        _ = attachment_metas
        return "默认目录" in str(user_message or "")

    def _infer_followup_primary_intent_from_state(
        self,
        *,
        user_message: str,
        route_state: dict[str, Any] | None,
        signals: dict[str, Any],
    ) -> str:
        _ = user_message, signals
        return str((route_state or {}).get("primary_intent") or "")

    def _looks_like_write_or_edit_action(self, text: str) -> bool:
        lowered = str(text or "").lower()
        markers = ("改", "修改", "改成", "翻成", "写成", "重写", "修复", "邮件", "write", "rewrite", "translate", "patch", "edit", "fix")
        return any(marker in lowered for marker in markers)


def build_layers(*, enable_tools: bool = True):
    agent = StubAgent()
    settings = StubSettings(enable_tools=enable_tools)
    extractor = RouterSignalExtractor(
        agent,
        news_hints=("news", "新闻", "今日", "today"),
        followup_reference_hints=("这个", "刚才", "上一个", "上一版", "按刚才", "继续", "that", "this", "previous"),
        followup_transform_hints=("改成", "翻成", "写成", "表格", "邮件", "修复", "判断", "rewrite", "translate"),
    )
    classifier = IntentClassifier(agent)
    policy_router = PolicyRouter(agent)
    verifier = RouteVerifier()
    return settings, extractor, classifier, policy_router, verifier


def run_pipeline(
    *,
    message: str,
    attachments: list[dict[str, Any]] | None = None,
    route_state: dict[str, Any] | None = None,
    inline_followup_context: bool = False,
    enable_tools: bool = True,
    force_rules_only: bool = False,
):
    settings, extractor, classifier, policy_router, verifier = build_layers(enable_tools=enable_tools)
    attachment_metas = list(attachments or [])

    signals = extractor.extract(
        user_message=message,
        attachment_metas=attachment_metas,
        settings=settings,
        route_state=route_state,
        inline_followup_context=inline_followup_context,
    )
    frame = classifier.resolve_frame(
        user_message=message,
        route_state=route_state,
        signals=signals,
    )
    candidates = classifier.generate_candidates(
        signals=signals,
        frame=frame,
    )
    decision, raw = classifier.score_decision(
        candidates=candidates,
        requested_model="gpt-test",
        user_message=message,
        summary="",
        attachment_metas=attachment_metas,
        settings=settings,
        signals=signals,
        frame=frame,
        force_rules_only=force_rules_only,
    )
    decision = classifier.postprocess_decision(decision=decision, signals=signals)
    fallback = policy_router.build_fallback_from_decision(
        decision=decision,
        frame=frame,
        settings=settings,
        signals=signals,
    )
    route = policy_router.route_from_decision(
        decision=decision,
        frame=frame,
        settings=settings,
        signals=signals,
        fallback=fallback,
        source_override=str(decision.source or ""),
        force_disable_llm_router=True,
    )
    route, notes = verifier.verify(
        decision=decision,
        route=route,
        signals=signals,
        frame=frame,
    )
    trace = build_route_trace(
        request_id="test-request",
        timestamp="2026-03-27T00:00:00+00:00",
        user_message=message,
        signals=signals,
        frame=frame,
        decision=decision,
        route=route,
        runtime_override_notes=[],
        runtime_override_actions=[],
    )
    return {
        "signals": signals,
        "frame": frame,
        "candidates": candidates,
        "decision": decision,
        "route": route,
        "raw": raw,
        "notes": notes,
        "trace": trace,
    }
