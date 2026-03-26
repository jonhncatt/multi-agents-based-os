from __future__ import annotations

from typing import Any

from app.execution_policy import execution_policy_spec, planner_enabled_for_policy
from app.intent_schema import ConversationFrame, IntentClassification, IntentDecision, RequestSignals, RouteDecision
from packages.office_modules.runtime_profiles import default_runtime_profile_for_route


_TASK_TYPE_TO_PRIMARY_INTENT = {
    "understanding": "understanding",
    "simple_understanding": "understanding",
    "inline_document_understanding": "understanding",
    "attachment_tooling": "understanding",
    "attachment_understanding": "understanding",
    "mixed_attachment": "understanding",
    "evidence_lookup": "evidence",
    "web_news": "web",
    "web_research": "web",
    "code_lookup": "code_lookup",
    "grounded_generation": "generation",
    "grounded_code_generation": "generation",
    "generation": "generation",
    "code_generation": "generation",
    "mixed_intent": "standard",
    "followup_transform": "standard",
    "meeting_minutes": "meeting_minutes",
    "simple_qa": "qa",
    "general_qa": "qa",
}

_TASK_TYPE_TO_EXECUTION_POLICY = {
    "understanding": "understanding_direct",
    "simple_understanding": "understanding_direct",
    "inline_document_understanding": "inline_document_understanding_direct",
    "attachment_tooling": "attachment_tooling_generic",
    "attachment_understanding": "attachment_holistic_understanding_with_tools",
    "mixed_attachment": "llm_router_attachment_ambiguity",
    "evidence_lookup": "evidence_full_pipeline",
    "web_news": "web_news_brief",
    "web_research": "web_research_full_pipeline",
    "code_lookup": "code_lookup_with_tools",
    "grounded_generation": "grounded_generation_pipeline",
    "grounded_code_generation": "grounded_generation_with_tools",
    "generation": "direct_generation",
    "code_generation": "generation_with_tools",
    "mixed_intent": "mixed_intent_planner_pipeline",
    "followup_transform": "followup_transform_pipeline",
    "meeting_minutes": "meeting_minutes_output",
    "simple_qa": "qa_direct",
    "general_qa": "llm_router_general_ambiguity",
    "standard": "standard_safe_pipeline",
}

_ALLOWED_PRIMARY_INTENTS = {
    "understanding",
    "evidence",
    "web",
    "code_lookup",
    "generation",
    "meeting_minutes",
    "qa",
    "standard",
}


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
        decision = IntentDecision(
            top_intent=str(intent.primary_intent or "standard"),
            second_intent=str((intent.secondary_intents or [""])[0] if intent.secondary_intents else ""),
            confidence=float(intent.confidence),
            mixed_intent=bool(intent.mixed_intent),
            inherited_from_state=str(intent.inherited_from_state or signals.inherited_primary_intent or ""),
            requires_tools=bool(intent.requires_tools),
            requires_grounding=bool(intent.requires_grounding),
            requires_web=bool(intent.requires_web),
            requires_local_lookup=bool(intent.requires_local_lookup),
            action_type=str(intent.action_type or "answer"),
            reason_short=str(intent.reason_short or ""),
            source=str(intent.source or "rules"),
            classifier_model=str(intent.classifier_model or ""),
            escalation_reason=str(intent.escalation_reason or ""),
        )
        frame = ConversationFrame(
            dominant_intent=str(decision.inherited_from_state or decision.top_intent or "standard"),
            last_route_policy=str(getattr(settings, "runtime_profile", "") or ""),
        )
        del user_message, attachment_metas
        return self.build_fallback_from_decision(
            decision=decision,
            frame=frame,
            settings=settings,
            signals=signals,
        )

    def build_fallback_from_decision(
        self,
        *,
        decision: IntentDecision,
        frame: ConversationFrame,
        settings: Any,
        signals: RequestSignals,
    ) -> dict[str, Any]:
        return self._base_route_payload(decision=decision, frame=frame, signals=signals, settings=settings)

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
        decision = IntentDecision(
            top_intent=str(intent.primary_intent or "standard"),
            second_intent=str((intent.secondary_intents or [""])[0] if intent.secondary_intents else ""),
            confidence=float(intent.confidence),
            mixed_intent=bool(intent.mixed_intent),
            inherited_from_state=str(intent.inherited_from_state or signals.inherited_primary_intent or ""),
            requires_tools=bool(intent.requires_tools),
            requires_grounding=bool(intent.requires_grounding),
            requires_web=bool(intent.requires_web),
            requires_local_lookup=bool(intent.requires_local_lookup),
            action_type=str(intent.action_type or "answer"),
            reason_short=str(intent.reason_short or ""),
            source=str(intent.source or "rules"),
            classifier_model=str(intent.classifier_model or ""),
            escalation_reason=str(intent.escalation_reason or ""),
        )
        frame = ConversationFrame(
            dominant_intent=str(decision.inherited_from_state or decision.top_intent or "standard"),
            pending_transform="rewrite_or_transform" if (signals.transform_followup_like and signals.reference_followup_like) else "",
            last_route_policy=str((signals.route_state or {}).get("execution_policy") or ""),
        )
        del user_message, attachment_metas
        return self.route_from_decision(
            decision=decision,
            frame=frame,
            settings=settings,
            signals=signals,
            fallback=fallback,
            source_override=source_override,
            force_disable_llm_router=force_disable_llm_router,
        )

    def route_from_decision(
        self,
        *,
        decision: IntentDecision,
        frame: ConversationFrame,
        settings: Any,
        signals: RequestSignals,
        fallback: dict[str, Any],
        source_override: str = "",
        force_disable_llm_router: bool = False,
    ) -> dict[str, Any]:
        base = self._base_route_payload(decision=decision, frame=frame, signals=signals, settings=settings)

        if bool(decision.requires_clarifying_route):
            routed = self._route_clarifying_safe(decision=decision, signals=signals, settings=settings)
        elif self._is_followup_transform(decision=decision, frame=frame, signals=signals):
            routed = self._route_followup_transform(decision=decision, frame=frame, signals=signals, settings=settings)
        elif self._prefers_grounded_generation(decision=decision):
            routed = self._route_generation(decision=decision, signals=signals, settings=settings)
        elif bool(decision.mixed_intent):
            routed = self._route_mixed(decision=decision, frame=frame, signals=signals, settings=settings)
        else:
            primary = str(decision.top_intent or "standard").strip().lower()
            if primary == "understanding":
                routed = self._route_understanding(decision=decision, frame=frame, signals=signals, settings=settings)
            elif primary == "evidence":
                routed = self._route_evidence(decision=decision, signals=signals, settings=settings)
            elif primary == "web":
                routed = self._route_web(decision=decision, signals=signals, settings=settings)
            elif primary == "code_lookup":
                routed = self._route_code_lookup(decision=decision, signals=signals, settings=settings)
            elif primary == "generation":
                routed = self._route_generation(decision=decision, signals=signals, settings=settings)
            elif primary == "meeting_minutes":
                routed = self._route_meeting_minutes(decision=decision, signals=signals, settings=settings)
            else:
                routed = self._route_standard(decision=decision, signals=signals, settings=settings)

        merged = {**fallback, **base, **routed}
        if not bool(getattr(settings, "enable_tools", False)):
            merged["use_worker_tools"] = False
            merged["use_web_prefetch"] = False

        if decision.classifier_model:
            merged["router_model"] = decision.classifier_model
        if source_override:
            merged["source"] = source_override
        if force_disable_llm_router:
            merged["needs_llm_router"] = False

        decision_payload = RouteDecision.model_validate(merged)
        return decision_payload.to_route_dict()

    def _base_route_payload(
        self,
        *,
        decision: IntentDecision,
        frame: ConversationFrame,
        signals: RequestSignals,
        settings: Any,
    ) -> dict[str, Any]:
        enable_tools = bool(getattr(settings, "enable_tools", False))
        secondaries: list[str] = []
        if decision.second_intent and decision.second_intent != decision.top_intent:
            secondaries.append(str(decision.second_intent))
        for item in decision.candidates[2:6]:
            intent = str(item.intent or "").strip().lower()
            if intent and intent not in secondaries and intent != decision.top_intent and float(item.score) > 0.0:
                secondaries.append(intent)

        return {
            "task_type": "standard",
            "complexity": "medium",
            "use_planner": True,
            "use_worker_tools": bool(enable_tools and decision.requires_tools),
            "use_reviewer": True,
            "use_revision": True,
            "use_structurer": False,
            "use_web_prefetch": bool(enable_tools and decision.requires_web),
            "use_conflict_detector": True,
            "specialists": [],
            "needs_llm_router": False,
            "reason": "policy_default",
            "summary": "默认策略路由。",
            "source": str(decision.source or "rules"),
            "router_model": str(decision.classifier_model or ""),
            "execution_policy": "standard_safe_pipeline",
            "runtime_profile": "evidence",
            "primary_intent": str(decision.top_intent or "standard"),
            "secondary_intents": secondaries,
            "requires_tools": bool(decision.requires_tools),
            "requires_grounding": bool(decision.requires_grounding),
            "requires_web": bool(decision.requires_web),
            "requires_local_lookup": bool(decision.requires_local_lookup),
            "action_type": str(decision.action_type or "answer"),
            "intent_confidence": float(decision.confidence),
            "intent_source": str(decision.source or "rules"),
            "intent_reason": str(decision.reason_short or ""),
            "mixed_intent": bool(decision.mixed_intent),
            "inherited_from_state": str(decision.inherited_from_state or frame.dominant_intent or ""),
            "escalation_reason": str(decision.escalation_reason or ""),
            "intent_candidates": [item.model_dump() for item in decision.candidates],
            "intent_margin": float(decision.margin),
            "frame_dominant_intent": str(frame.dominant_intent or ""),
            "route_verified": False,
            "verifier_notes": [],
            "verifier_actions": [],
            "spec_lookup_request": bool(signals.spec_lookup_request),
            "evidence_required_mode": bool(signals.evidence_required),
            "default_root_search": bool(signals.default_root_search),
        }

    def _route_understanding(
        self,
        *,
        decision: IntentDecision,
        frame: ConversationFrame,
        signals: RequestSignals,
        settings: Any,
    ) -> dict[str, Any]:
        del frame
        enable_tools = bool(getattr(settings, "enable_tools", False))
        needs_tools = bool(signals.has_attachments or signals.attachment_needs_tooling or decision.requires_tools)
        if needs_tools and enable_tools:
            return {
                "task_type": "understanding",
                "complexity": "medium" if signals.has_attachments else "low",
                "use_planner": False,
                "use_worker_tools": True,
                "use_reviewer": False,
                "use_revision": False,
                "use_structurer": False,
                "use_web_prefetch": False,
                "use_conflict_detector": False,
                "specialists": ["file_reader", "summarizer"],
                "reason": "policy_understanding_with_tools",
                "summary": "理解任务需要读取上下文，走 attachment understanding with tools。",
                "execution_policy": "attachment_holistic_understanding_with_tools",
                "runtime_profile": "explainer",
            }
        return {
            "task_type": "understanding",
            "complexity": "low",
            "use_planner": False,
            "use_worker_tools": False,
            "use_reviewer": False,
            "use_revision": False,
            "use_structurer": False,
            "use_web_prefetch": False,
            "use_conflict_detector": False,
            "specialists": ["summarizer"] if signals.has_attachments else [],
            "reason": "policy_understanding_direct",
            "summary": "理解任务直接回答。",
            "execution_policy": "understanding_direct",
            "runtime_profile": "explainer",
        }

    def _route_evidence(
        self,
        *,
        decision: IntentDecision,
        signals: RequestSignals,
        settings: Any,
    ) -> dict[str, Any]:
        enable_tools = bool(getattr(settings, "enable_tools", False))
        use_worker_tools = bool(enable_tools and (decision.requires_tools or signals.has_attachments or signals.evidence_required))
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
            "specialists": ["file_reader"] if use_worker_tools else [],
            "reason": "policy_evidence",
            "summary": "证据/出处请求。",
            "execution_policy": "evidence_full_pipeline" if use_worker_tools else "evidence_lookup",
            "runtime_profile": "evidence",
        }

    def _route_web(
        self,
        *,
        decision: IntentDecision,
        signals: RequestSignals,
        settings: Any,
    ) -> dict[str, Any]:
        del decision
        enable_tools = bool(getattr(settings, "enable_tools", False))
        return {
            "task_type": "web_research",
            "complexity": "medium",
            "use_planner": True,
            "use_worker_tools": enable_tools,
            "use_reviewer": True,
            "use_revision": True,
            "use_structurer": True,
            "use_web_prefetch": bool(enable_tools and signals.web_request),
            "use_conflict_detector": True,
            "specialists": ["researcher"],
            "reason": "policy_web",
            "summary": "联网信息请求。",
            "execution_policy": "web_research_full_pipeline" if enable_tools else "web_research",
            "runtime_profile": "evidence",
        }

    def _route_code_lookup(
        self,
        *,
        decision: IntentDecision,
        signals: RequestSignals,
        settings: Any,
    ) -> dict[str, Any]:
        del decision, signals
        enable_tools = bool(getattr(settings, "enable_tools", False))
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
            "reason": "policy_code_lookup",
            "summary": "本地代码定位请求。",
            "execution_policy": "code_lookup_with_tools" if enable_tools else "code_lookup",
            "runtime_profile": "explainer",
        }

    def _route_generation(
        self,
        *,
        decision: IntentDecision,
        signals: RequestSignals,
        settings: Any,
    ) -> dict[str, Any]:
        grounded = bool(decision.requires_grounding or signals.grounded_code_generation_context)
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
                "reason": "policy_grounded_generation",
                "summary": "基于现有内容的生成请求。",
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
            "reason": "policy_direct_generation",
            "summary": "非 grounded 生成请求。",
            "execution_policy": "direct_generation",
            "runtime_profile": "explainer",
        }

    def _route_meeting_minutes(
        self,
        *,
        decision: IntentDecision,
        signals: RequestSignals,
        settings: Any,
    ) -> dict[str, Any]:
        del decision
        return {
            "task_type": "meeting_minutes",
            "complexity": "medium",
            "use_planner": True,
            "use_worker_tools": bool(getattr(settings, "enable_tools", False) and signals.has_attachments),
            "use_reviewer": False,
            "use_revision": False,
            "use_structurer": True,
            "use_web_prefetch": False,
            "use_conflict_detector": False,
            "specialists": ["summarizer", "file_reader"] if signals.has_attachments else ["summarizer"],
            "reason": "policy_meeting_minutes",
            "summary": "会议纪要任务。",
            "execution_policy": "meeting_minutes_pipeline",
            "runtime_profile": "explainer",
        }

    def _route_standard(
        self,
        *,
        decision: IntentDecision,
        signals: RequestSignals,
        settings: Any,
    ) -> dict[str, Any]:
        del decision
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
            "reason": "policy_standard",
            "summary": "标准安全链路。",
            "execution_policy": "standard_safe_pipeline",
            "runtime_profile": "evidence",
        }

    def _route_mixed(
        self,
        *,
        decision: IntentDecision,
        frame: ConversationFrame,
        signals: RequestSignals,
        settings: Any,
    ) -> dict[str, Any]:
        del frame
        pair = (str(decision.top_intent or "").strip().lower(), str(decision.second_intent or "").strip().lower())
        specialists: list[str] = []
        if pair == ("understanding", "generation"):
            specialists = ["summarizer", "file_reader"]
        elif pair == ("understanding", "meeting_minutes"):
            specialists = ["summarizer", "file_reader"]
        elif pair == ("evidence", "generation"):
            specialists = ["file_reader"]
        if not specialists and signals.has_attachments:
            specialists = ["file_reader", "summarizer"]

        return {
            "task_type": "mixed_intent",
            "complexity": "high",
            "use_planner": True,
            "use_worker_tools": bool(getattr(settings, "enable_tools", False) and (decision.requires_tools or signals.has_attachments)),
            "use_reviewer": True,
            "use_revision": True,
            "use_structurer": False,
            "use_web_prefetch": bool(getattr(settings, "enable_tools", False) and decision.requires_web),
            "use_conflict_detector": True,
            "specialists": specialists,
            "reason": "policy_mixed_intent",
            "summary": "混合意图任务，走 mixed planner pipeline。",
            "execution_policy": "mixed_intent_planner_pipeline",
            "runtime_profile": "evidence",
        }

    def _route_followup_transform(
        self,
        *,
        decision: IntentDecision,
        frame: ConversationFrame,
        signals: RequestSignals,
        settings: Any,
    ) -> dict[str, Any]:
        del frame
        return {
            "task_type": "followup_transform",
            "complexity": "medium",
            "use_planner": True,
            "use_worker_tools": bool(getattr(settings, "enable_tools", False) and (decision.requires_tools or signals.has_attachments)),
            "use_reviewer": bool(decision.requires_grounding),
            "use_revision": bool(decision.requires_grounding),
            "use_structurer": False,
            "use_web_prefetch": bool(getattr(settings, "enable_tools", False) and decision.requires_web),
            "use_conflict_detector": bool(decision.requires_grounding),
            "specialists": ["summarizer", "file_reader"] if signals.has_attachments else ["summarizer"],
            "reason": "policy_followup_transform",
            "summary": "继承态 follow-up 变换任务。",
            "execution_policy": "followup_transform_pipeline",
            "runtime_profile": "explainer",
        }

    def _route_clarifying_safe(
        self,
        *,
        decision: IntentDecision,
        signals: RequestSignals,
        settings: Any,
    ) -> dict[str, Any]:
        del decision, signals, settings
        return {
            "task_type": "standard",
            "complexity": "medium",
            "use_planner": True,
            "use_worker_tools": False,
            "use_reviewer": True,
            "use_revision": True,
            "use_structurer": False,
            "use_web_prefetch": False,
            "use_conflict_detector": True,
            "specialists": [],
            "reason": "policy_clarifying_safe",
            "summary": "低置信度/高歧义，走安全澄清链路。",
            "execution_policy": "standard_safe_pipeline",
            "runtime_profile": "evidence",
        }

    def _is_followup_transform(
        self,
        *,
        decision: IntentDecision,
        frame: ConversationFrame,
        signals: RequestSignals,
    ) -> bool:
        inherited = str(decision.inherited_from_state or "").strip().lower()
        inherited_active = bool(inherited and inherited != "standard")
        followup_context = bool(signals.inline_followup_context or inherited_active)

        if frame.pending_transform == "rewrite_or_transform" and followup_context:
            return True
        if followup_context and signals.short_followup_like and signals.transform_followup_like and signals.reference_followup_like:
            return True
        return bool(
            inherited_active
            and signals.transform_followup_like
            and signals.reference_followup_like
        )

    def _prefers_grounded_generation(self, *, decision: IntentDecision) -> bool:
        intents = {str(decision.top_intent or "").strip().lower(), str(decision.second_intent or "").strip().lower()}
        return bool(
            decision.requires_grounding
            and "generation" in intents
            and "code_lookup" in intents
        )

    def task_type_to_primary_intent(self, task_type: str) -> str:
        normalized = str(task_type or "").strip().lower()
        return str(_TASK_TYPE_TO_PRIMARY_INTENT.get(normalized, "standard"))

    def task_type_to_execution_policy(self, task_type: str) -> str:
        normalized = str(task_type or "").strip().lower()
        return str(_TASK_TYPE_TO_EXECUTION_POLICY.get(normalized, "standard_safe_pipeline"))

    def normalize_primary_intent(self, value: str, *, task_type: str = "") -> str:
        normalized = str(value or "").strip().lower()
        if normalized in _ALLOWED_PRIMARY_INTENTS:
            return normalized
        if task_type:
            return self.task_type_to_primary_intent(task_type)
        return "standard"

    def normalize_route(
        self,
        *,
        route: dict[str, Any],
        fallback: dict[str, Any],
        settings: Any,
    ) -> dict[str, Any]:
        normalized = dict(fallback)
        normalized.update(route or {})

        normalized["task_type"] = str(normalized.get("task_type") or fallback.get("task_type") or "standard").strip()
        complexity = str(normalized.get("complexity") or fallback.get("complexity") or "medium").strip().lower()
        if complexity not in {"low", "medium", "high"}:
            complexity = "medium"
        normalized["complexity"] = complexity
        normalized["specialists"] = self._agent._normalize_specialists(
            normalized.get("specialists") or fallback.get("specialists") or []
        )
        normalized["primary_intent"] = self.normalize_primary_intent(
            str(normalized.get("primary_intent") or fallback.get("primary_intent") or ""),
            task_type=normalized["task_type"],
        )
        normalized["execution_policy"] = (
            str(normalized.get("execution_policy") or fallback.get("execution_policy") or "").strip()
            or self.task_type_to_execution_policy(normalized["task_type"])
        )
        normalized["runtime_profile"] = (
            str(normalized.get("runtime_profile") or fallback.get("runtime_profile") or "").strip()
            or default_runtime_profile_for_route(normalized)
        )

        for key in (
            "use_planner",
            "use_worker_tools",
            "use_reviewer",
            "use_revision",
            "use_structurer",
            "use_web_prefetch",
            "use_conflict_detector",
            "needs_llm_router",
            "route_verified",
        ):
            normalized[key] = bool(normalized.get(key))
        normalized["verifier_notes"] = self._agent._normalize_string_list(
            normalized.get("verifier_notes") or [],
            limit=12,
            item_limit=220,
        )
        normalized["verifier_actions"] = self._agent._normalize_string_list(
            normalized.get("verifier_actions") or [],
            limit=12,
            item_limit=120,
        )

        raw_spec_lookup_request = bool(normalized.get("spec_lookup_request"))
        raw_evidence_required_mode = bool(normalized.get("evidence_required_mode"))
        raw_default_root_search = bool(normalized.get("default_root_search"))

        if not bool(getattr(settings, "enable_tools", False)):
            normalized["use_worker_tools"] = False
            normalized["use_web_prefetch"] = False

        policy_spec = execution_policy_spec(normalized["execution_policy"])
        normalized["use_planner"] = planner_enabled_for_policy(
            normalized["execution_policy"],
            use_worker_tools=bool(normalized["use_worker_tools"]),
        )
        normalized["use_reviewer"] = policy_spec.reviewer
        normalized["use_revision"] = policy_spec.revision
        normalized["use_structurer"] = policy_spec.structurer
        normalized["use_conflict_detector"] = policy_spec.conflict_detector

        if not normalized["use_worker_tools"]:
            normalized["use_web_prefetch"] = False

        route_task_type = str(normalized.get("task_type") or "").strip().lower()
        normalized["spec_lookup_request"] = raw_spec_lookup_request and route_task_type == "evidence_lookup"
        normalized["evidence_required_mode"] = (
            raw_evidence_required_mode
            and route_task_type == "evidence_lookup"
            and bool(normalized["use_worker_tools"])
        )
        normalized["default_root_search"] = raw_default_root_search and bool(normalized["use_worker_tools"])
        review_chain_required = bool(
            normalized["spec_lookup_request"]
            or normalized["evidence_required_mode"]
            or route_task_type in {"evidence_lookup", "web_research", "grounded_generation", "mixed_intent"}
            or str(normalized.get("execution_policy") or "").strip().lower()
            in {"grounded_generation_pipeline", "mixed_intent_planner_pipeline"}
        )
        if not review_chain_required:
            normalized["use_reviewer"] = False
            normalized["use_revision"] = False
            normalized["use_structurer"] = False
            normalized["use_conflict_detector"] = False

        normalized["reason"] = str(normalized.get("reason") or fallback.get("reason") or "").strip()
        normalized["source"] = str(normalized.get("source") or fallback.get("source") or "rules").strip() or "rules"
        normalized["summary"] = (
            str(normalized.get("summary") or "").strip()
            or f"task_type={normalized['task_type']}, complexity={normalized['complexity']}"
        )
        normalized["router_model"] = str(normalized.get("router_model") or "").strip()
        return normalized
