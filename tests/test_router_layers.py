from __future__ import annotations

from typing import Any

from app.intent_classifier import IntentClassifier
from app.policy_router import PolicyRouter
from app.router_signals import RouterSignalExtractor


class _StubSettings:
    def __init__(self, *, enable_tools: bool = True) -> None:
        self.enable_tools = enable_tools


class _StubAuthManager:
    def auth_summary(self) -> dict[str, Any]:
        return {"available": False, "reason": "stub_no_llm"}


class _StubAgent:
    def __init__(self) -> None:
        self._auth_manager = _StubAuthManager()

    def _looks_like_context_dependent_followup(self, text: str) -> bool:
        lowered = str(text or "").strip().lower()
        return lowered in {"继续", "继续吧", "改成邮件", "翻成日文"} or ("继续" in lowered) or ("改成" in lowered) or ("翻成" in lowered)

    def _looks_like_spec_lookup_request(self, user_message: str, attachment_metas: list[dict[str, Any]]) -> bool:
        _ = attachment_metas
        lowered = str(user_message or "").lower()
        return "spec" in lowered

    def _requires_evidence_mode(self, user_message: str, attachment_metas: list[dict[str, Any]]) -> bool:
        _ = attachment_metas
        lowered = str(user_message or "").lower()
        return ("证据" in lowered) or ("出处" in lowered) or ("来源" in lowered)

    def _attachment_needs_tooling(self, meta: dict[str, Any]) -> bool:
        return bool(meta.get("needs_tooling"))

    def _attachment_is_inline_parseable(self, meta: dict[str, Any]) -> bool:
        return bool(meta.get("inline_parseable", not bool(meta.get("needs_tooling"))))

    def _looks_like_inline_document_payload(self, user_message: str) -> bool:
        return "```" in str(user_message or "")

    def _looks_like_understanding_request(self, user_message: str) -> bool:
        lowered = str(user_message or "").lower()
        return ("解释" in lowered) or ("说明" in lowered) or ("understand" in lowered)

    def _looks_like_holistic_document_explanation_request(self, user_message: str) -> bool:
        lowered = str(user_message or "").lower()
        return ("整体" in lowered) or ("全文" in lowered)

    def _looks_like_source_trace_request(self, user_message: str) -> bool:
        lowered = str(user_message or "").lower()
        return ("出处" in lowered) or ("来源" in lowered)

    def _looks_like_explicit_tool_confirmation(self, user_message: str) -> bool:
        return str(user_message or "").strip() in {"继续", "执行"}

    def _looks_like_meeting_minutes_request(self, user_message: str) -> bool:
        return "会议纪要" in str(user_message or "")

    def _looks_like_internal_ticket_reference(self, user_message: str) -> bool:
        return "jira" in str(user_message or "").lower()

    def _request_likely_requires_tools(self, user_message: str, attachment_metas: list[dict[str, Any]]) -> bool:
        if attachment_metas:
            return True
        lowered = str(user_message or "").lower()
        tool_markers = (
            "查找",
            "定位",
            "读取",
            "上网",
            "新闻",
            "today",
            "web",
            "今日",
            "基于现有代码",
            "修改代码",
            "默认目录",
        )
        return any(marker in lowered for marker in tool_markers)

    def _looks_like_local_code_lookup_request(self, user_message: str, attachment_metas: list[dict[str, Any]]) -> bool:
        _ = attachment_metas
        lowered = str(user_message or "").lower()
        return ("函数" in lowered) or ("本地代码" in lowered)

    def _message_has_explicit_local_path(self, user_message: str) -> bool:
        lowered = str(user_message or "").lower()
        return ("/" in lowered) and ("." in lowered)

    def _has_file_like_lookup_token(self, text: str) -> bool:
        lowered = str(text or "").lower()
        return any(token in lowered for token in (".py", ".ts", ".md", ".json"))

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
        markers = ("改", "修改", "改成", "翻成", "写成", "重写", "rewrite", "translate", "邮件", "日文")
        return any(marker in lowered for marker in markers)

    def _classify_primary_intent(
        self,
        *,
        user_message: str,
        attachment_metas: list[dict[str, Any]],
        route_state: dict[str, Any] | None,
        signals: dict[str, Any],
    ) -> str:
        lowered = str(user_message or "").lower()
        inherited = str(signals.get("inherited_primary_intent") or (route_state or {}).get("primary_intent") or "").strip().lower()

        if inherited and (len(lowered.strip()) <= 16 or any(token in lowered for token in ("继续", "改成", "翻成"))):
            return inherited
        if signals.get("source_trace_request") or signals.get("spec_lookup_request") or signals.get("evidence_required"):
            return "evidence"
        if signals.get("meeting_minutes_request"):
            return "meeting_minutes"
        if signals.get("web_request"):
            return "web"
        if signals.get("local_code_lookup_request"):
            return "code_lookup"
        if signals.get("has_attachments") and signals.get("understanding_request"):
            return "understanding"
        if any(token in lowered for token in ("基于现有代码", "修改代码", "生成代码", "新增实现", "重构实现")):
            return "generation"
        if signals.get("request_requires_tools"):
            return "standard"
        return "standard"


def _build_layers(*, enable_tools: bool = True):
    agent = _StubAgent()
    settings = _StubSettings(enable_tools=enable_tools)
    extractor = RouterSignalExtractor(
        agent,
        news_hints=("news", "新闻", "今日", "today"),
        followup_reference_hints=("这个", "上一个", "上一版", "继续", "前面"),
        followup_transform_hints=("改成", "翻成", "写成", "表格", "邮件"),
    )
    classifier = IntentClassifier(agent)
    policy_router = PolicyRouter(agent)
    return agent, settings, extractor, classifier, policy_router


def _classify_and_route(
    *,
    message: str,
    attachments: list[dict[str, Any]] | None = None,
    route_state: dict[str, Any] | None = None,
    inline_followup_context: bool = False,
    enable_tools: bool = True,
):
    _, settings, extractor, classifier, policy_router = _build_layers(enable_tools=enable_tools)
    attachment_metas = list(attachments or [])
    signals = extractor.extract(
        user_message=message,
        attachment_metas=attachment_metas,
        settings=settings,
        route_state=route_state,
        inline_followup_context=inline_followup_context,
    )
    intent, raw = classifier.classify(
        requested_model="gpt-test",
        user_message=message,
        summary="",
        attachment_metas=attachment_metas,
        settings=settings,
        route_state=route_state,
        signals=signals,
    )
    fallback = policy_router.build_fallback(
        intent=intent,
        user_message=message,
        attachment_metas=attachment_metas,
        settings=settings,
        signals=signals,
    )
    route = policy_router.route(
        intent=intent,
        user_message=message,
        attachment_metas=attachment_metas,
        settings=settings,
        signals=signals,
        fallback=fallback,
        source_override=str(intent.source or ""),
        force_disable_llm_router=True,
    )
    return signals, intent, route, raw


def test_attachment_holistic_understanding_routes_to_understanding_pipeline() -> None:
    signals, intent, route, _ = _classify_and_route(
        message="请解释这个附件的整体内容",
        attachments=[{"inline_parseable": True, "needs_tooling": False}],
    )
    assert signals.has_attachments is True
    assert intent.primary_intent == "understanding"
    assert route["execution_policy"] == "attachment_holistic_understanding_with_tools"
    assert route["runtime_profile"] == "explainer"


def test_evidence_request_routes_to_evidence_pipeline() -> None:
    _, intent, route, _ = _classify_and_route(message="请给出这个结论的出处和证据")
    assert intent.primary_intent == "evidence"
    assert route["execution_policy"] in {"evidence_lookup", "evidence_full_pipeline"}
    assert route["use_planner"] is True
    assert route["use_reviewer"] is True


def test_local_function_lookup_routes_to_code_lookup() -> None:
    _, intent, route, _ = _classify_and_route(message="帮我定位这个函数在哪个文件")
    assert intent.primary_intent == "code_lookup"
    assert route["execution_policy"] == "code_lookup_with_tools"
    assert route["use_worker_tools"] is True


def test_today_news_routes_to_web_pipeline() -> None:
    _, intent, route, _ = _classify_and_route(message="今天 AI 新闻有什么")
    assert intent.primary_intent == "web"
    assert route["execution_policy"] == "web_research_full_pipeline"
    assert route["use_web_prefetch"] is True


def test_grounded_generation_routes_to_grounded_pipeline() -> None:
    _, intent, route, _ = _classify_and_route(message="基于现有代码修改 /repo/app/main.py 里的实现")
    assert intent.primary_intent == "generation"
    assert intent.requires_grounding is True
    assert route["execution_policy"] == "grounded_generation_pipeline"
    assert route["use_planner"] is True
    assert route["use_reviewer"] is True


def test_followup_inherits_intent_for_continue_transform_translate() -> None:
    for followup in ("继续", "改成邮件", "翻成日文"):
        _, intent, route, _ = _classify_and_route(
            message=followup,
            route_state={"primary_intent": "understanding"},
            inline_followup_context=True,
        )
        assert intent.primary_intent == "understanding"
        assert intent.inherited_from_state == "understanding"
        assert route["primary_intent"] == "understanding"


def test_mixed_intent_understanding_and_generation_enables_planner() -> None:
    _, intent, route, _ = _classify_and_route(
        message="解释附件并整理成表格后写成邮件",
        attachments=[{"inline_parseable": True, "needs_tooling": False}],
    )
    assert intent.primary_intent == "understanding"
    assert intent.mixed_intent is True
    assert route["use_planner"] is True


def test_low_confidence_intent_falls_back_to_standard_safe_pipeline() -> None:
    _, intent, route, _ = _classify_and_route(message="嗯")
    assert intent.confidence < 0.60
    assert route["execution_policy"] == "standard_safe_pipeline"
    assert route["reason"] == "intent_low_confidence_standard_fallback"
