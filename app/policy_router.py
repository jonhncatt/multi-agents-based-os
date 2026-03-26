from __future__ import annotations

from typing import Any

from app.intent_classifier import INTENT_LOW_CONFIDENCE_THRESHOLD
from app.intent_schema import IntentClassification, RequestSignals, RouteDecision


class PolicyRouter:
    def __init__(self, agent: Any) -> None:
        self._agent = agent

    def build_fallback(
        self,
        *,
        intent: IntentClassification,
        user_message: str,
        attachment_metas: list[dict[str, Any]],
        settings: Any,
        signals: RequestSignals,
    ) -> dict[str, Any]:
        del user_message, attachment_metas
        return self._base_route_payload(intent=intent, signals=signals, settings=settings)

    def route(
        self,
        *,
        intent: IntentClassification,
        user_message: str,
        attachment_metas: list[dict[str, Any]],
        settings: Any,
        signals: RequestSignals,
        fallback: dict[str, Any],
        source_override: str = "",
        force_disable_llm_router: bool = False,
    ) -> dict[str, Any]:
        del user_message, attachment_metas
        base = self._base_route_payload(intent=intent, signals=signals, settings=settings)

        if float(intent.confidence) < INTENT_LOW_CONFIDENCE_THRESHOLD:
            routed = self._route_standard(intent=intent, signals=signals, settings=settings)
            routed["reason"] = "intent_low_confidence_standard_fallback"
            routed["summary"] = "意图置信度过低，回退到 standard_safe_pipeline。"
        else:
            primary = str(intent.primary_intent or "").strip().lower()
            if primary == "understanding":
                routed = self._route_understanding(intent=intent, signals=signals, settings=settings)
            elif primary == "evidence":
                routed = self._route_evidence(intent=intent, signals=signals, settings=settings)
            elif primary == "web":
                routed = self._route_web(intent=intent, signals=signals, settings=settings)
            elif primary == "code_lookup":
                routed = self._route_code_lookup(intent=intent, signals=signals, settings=settings)
            elif primary == "generation":
                routed = self._route_generation(intent=intent, signals=signals, settings=settings)
            elif primary == "meeting_minutes":
                routed = self._route_meeting_minutes(intent=intent, signals=signals, settings=settings)
            else:
                routed = self._route_standard(intent=intent, signals=signals, settings=settings)

        merged = {**fallback, **base, **routed}

        if not bool(getattr(settings, "enable_tools", False)):
            merged["use_worker_tools"] = False
            merged["use_web_prefetch"] = False

        if intent.classifier_model:
            merged["router_model"] = intent.classifier_model

        if source_override:
            merged["source"] = source_override

        if force_disable_llm_router:
            merged["needs_llm_router"] = False

        decision = RouteDecision.model_validate(merged)
        return decision.to_route_dict()

    def _base_route_payload(
        self,
        *,
        intent: IntentClassification,
        signals: RequestSignals,
        settings: Any,
    ) -> dict[str, Any]:
        enable_tools = bool(getattr(settings, "enable_tools", False))
        return {
            "task_type": "standard",
            "complexity": "medium",
            "use_planner": True,
            "use_worker_tools": bool(enable_tools and (intent.requires_tools or signals.request_requires_tools)),
            "use_reviewer": True,
            "use_revision": True,
            "use_structurer": False,
            "use_web_prefetch": bool(enable_tools and signals.web_request),
            "use_conflict_detector": True,
            "specialists": [],
            "needs_llm_router": False,
            "reason": "policy_default",
            "summary": "默认策略路由。",
            "source": str(intent.source or "rules_intent_classifier"),
            "router_model": str(intent.classifier_model or ""),
            "execution_policy": "standard_safe_pipeline",
            "runtime_profile": "evidence",
            "primary_intent": intent.primary_intent,
            "secondary_intents": list(intent.secondary_intents),
            "requires_tools": bool(intent.requires_tools),
            "requires_grounding": bool(intent.requires_grounding),
            "requires_web": bool(intent.requires_web),
            "requires_local_lookup": bool(intent.requires_local_lookup),
            "action_type": intent.action_type,
            "intent_confidence": float(intent.confidence),
            "intent_source": str(intent.source or "rules_intent_classifier"),
            "intent_reason": str(intent.reason_short or ""),
            "mixed_intent": bool(intent.mixed_intent),
            "inherited_from_state": str(intent.inherited_from_state or ""),
            "escalation_reason": str(intent.escalation_reason or ""),
            "spec_lookup_request": bool(signals.spec_lookup_request),
            "evidence_required_mode": bool(signals.evidence_required),
            "default_root_search": bool(signals.default_root_search),
        }

    def _route_understanding(
        self,
        *,
        intent: IntentClassification,
        signals: RequestSignals,
        settings: Any,
    ) -> dict[str, Any]:
        enable_tools = bool(getattr(settings, "enable_tools", False))
        mixed_followup = bool(
            intent.mixed_intent
            or (signals.reference_followup_like and signals.transform_followup_like)
            or signals.ambiguity_score >= 0.55
        )
        requires_attachment_tooling = bool(signals.has_attachments or signals.attachment_needs_tooling or signals.request_requires_tools)
        use_worker_tools = bool(enable_tools and requires_attachment_tooling)

        if use_worker_tools:
            execution_policy = "attachment_holistic_understanding_with_tools"
            task_type = "attachment_understanding"
            specialists = ["file_reader", "summarizer"]
            summary = "理解类任务包含附件/工具需求，先读后答。"
        else:
            execution_policy = "understanding_direct"
            task_type = "understanding"
            specialists = ["summarizer"] if signals.has_attachments else []
            summary = "理解类任务，直接解释。"

        if mixed_followup:
            summary = "理解任务出现混合意图跟进，启用 planner 做拆解。"

        return {
            "task_type": task_type,
            "complexity": "medium" if signals.has_attachments else "low",
            "use_planner": bool(mixed_followup),
            "use_worker_tools": use_worker_tools,
            "use_reviewer": False,
            "use_revision": False,
            "use_structurer": False,
            "use_web_prefetch": False,
            "use_conflict_detector": False,
            "specialists": specialists,
            "needs_llm_router": False,
            "reason": "policy_understanding",
            "summary": summary,
            "execution_policy": execution_policy,
            "runtime_profile": "explainer",
        }

    def _route_evidence(
        self,
        *,
        intent: IntentClassification,
        signals: RequestSignals,
        settings: Any,
    ) -> dict[str, Any]:
        enable_tools = bool(getattr(settings, "enable_tools", False))
        use_worker_tools = bool(enable_tools and (intent.requires_tools or signals.has_attachments or signals.request_requires_tools))
        execution_policy = "evidence_full_pipeline" if use_worker_tools else "evidence_lookup"
        return {
            "task_type": "evidence_lookup",
            "complexity": "high" if signals.has_attachments else "medium",
            "use_planner": True,
            "use_worker_tools": use_worker_tools,
            "use_reviewer": True,
            "use_revision": True,
            "use_structurer": True,
            "use_web_prefetch": False,
            "use_conflict_detector": True,
            "specialists": ["file_reader"] if signals.has_attachments else [],
            "needs_llm_router": False,
            "reason": "policy_evidence",
            "summary": "证据/出处请求，走 evidence pipeline。",
            "execution_policy": execution_policy,
            "runtime_profile": "evidence",
        }

    def _route_web(
        self,
        *,
        intent: IntentClassification,
        signals: RequestSignals,
        settings: Any,
    ) -> dict[str, Any]:
        del intent
        enable_tools = bool(getattr(settings, "enable_tools", False))
        execution_policy = "web_research_full_pipeline" if enable_tools else "web_research"
        return {
            "task_type": "web_research",
            "complexity": "medium",
            "use_planner": True,
            "use_worker_tools": enable_tools,
            "use_reviewer": True,
            "use_revision": True,
            "use_structurer": True,
            "use_web_prefetch": enable_tools,
            "use_conflict_detector": True,
            "specialists": ["researcher"],
            "needs_llm_router": False,
            "reason": "policy_web_research",
            "summary": "联网请求，走 web research pipeline。",
            "execution_policy": execution_policy,
            "runtime_profile": "evidence",
        }

    def _route_code_lookup(
        self,
        *,
        intent: IntentClassification,
        signals: RequestSignals,
        settings: Any,
    ) -> dict[str, Any]:
        del intent, signals
        enable_tools = bool(getattr(settings, "enable_tools", False))
        execution_policy = "code_lookup_with_tools" if enable_tools else "code_lookup"
        return {
            "task_type": "code_lookup",
            "complexity": "medium",
            "use_planner": False,
            "use_worker_tools": enable_tools,
            "use_reviewer": False,
            "use_revision": False,
            "use_structurer": False,
            "use_web_prefetch": False,
            "use_conflict_detector": False,
            "specialists": ["file_reader"] if enable_tools else [],
            "needs_llm_router": False,
            "reason": "policy_code_lookup",
            "summary": "本地函数定位任务，优先启用读取工具链。",
            "execution_policy": execution_policy,
            "runtime_profile": "explainer",
        }

    def _route_generation(
        self,
        *,
        intent: IntentClassification,
        signals: RequestSignals,
        settings: Any,
    ) -> dict[str, Any]:
        grounded = bool(intent.requires_grounding or signals.grounded_code_generation_context)
        if grounded:
            return {
                "task_type": "grounded_generation",
                "complexity": "high",
                "use_planner": True,
                "use_worker_tools": bool(getattr(settings, "enable_tools", False)),
                "use_reviewer": True,
                "use_revision": True,
                "use_structurer": False,
                "use_web_prefetch": False,
                "use_conflict_detector": True,
                "specialists": ["file_reader"] if bool(getattr(settings, "enable_tools", False)) else [],
                "needs_llm_router": False,
                "reason": "policy_grounded_generation",
                "summary": "基于现有代码/附件的生成请求，走 grounded generation pipeline。",
                "execution_policy": "grounded_generation_pipeline",
                "runtime_profile": "evidence",
            }

        return {
            "task_type": "generation",
            "complexity": "medium",
            "use_planner": False,
            "use_worker_tools": False,
            "use_reviewer": False,
            "use_revision": False,
            "use_structurer": False,
            "use_web_prefetch": False,
            "use_conflict_detector": False,
            "specialists": [],
            "needs_llm_router": False,
            "reason": "policy_direct_generation",
            "summary": "非 grounded 生成请求，direct generation 直出。",
            "execution_policy": "direct_generation",
            "runtime_profile": "explainer",
        }

    def _route_meeting_minutes(
        self,
        *,
        intent: IntentClassification,
        signals: RequestSignals,
        settings: Any,
    ) -> dict[str, Any]:
        del intent
        enable_tools = bool(getattr(settings, "enable_tools", False))
        return {
            "task_type": "meeting_minutes",
            "complexity": "medium",
            "use_planner": True,
            "use_worker_tools": bool(enable_tools and signals.has_attachments),
            "use_reviewer": False,
            "use_revision": False,
            "use_structurer": True,
            "use_web_prefetch": False,
            "use_conflict_detector": False,
            "specialists": ["summarizer", "file_reader"] if signals.has_attachments else ["summarizer"],
            "needs_llm_router": False,
            "reason": "policy_meeting_minutes",
            "summary": "会议纪要任务，走 planner + structurer。",
            "execution_policy": "meeting_minutes_pipeline",
            "runtime_profile": "explainer",
        }

    def _route_standard(
        self,
        *,
        intent: IntentClassification,
        signals: RequestSignals,
        settings: Any,
    ) -> dict[str, Any]:
        del intent
        enable_tools = bool(getattr(settings, "enable_tools", False))
        return {
            "task_type": "standard",
            "complexity": "medium",
            "use_planner": True,
            "use_worker_tools": bool(enable_tools and signals.request_requires_tools),
            "use_reviewer": True,
            "use_revision": True,
            "use_structurer": False,
            "use_web_prefetch": bool(enable_tools and signals.web_request),
            "use_conflict_detector": True,
            "specialists": [],
            "needs_llm_router": False,
            "reason": "policy_standard_safe",
            "summary": "标准安全流水线。",
            "execution_policy": "standard_safe_pipeline",
            "runtime_profile": "evidence",
        }
