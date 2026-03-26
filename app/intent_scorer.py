from __future__ import annotations

import json
from typing import Any

from app.intent_constants import (
    INTENT_HIGH_AMBIGUITY_THRESHOLD,
    INTENT_LOW_CONFIDENCE_THRESHOLD,
    INTENT_MARGIN_MIXED_THRESHOLD,
)
from app.intent_schema import ConversationFrame, IntentDecision, IntentScore, RequestSignals


_ALLOWED_INTENTS = {
    "understanding",
    "evidence",
    "web",
    "code_lookup",
    "generation",
    "meeting_minutes",
    "qa",
    "standard",
}
_ALLOWED_ACTION_TYPES = {"answer", "search", "read", "modify", "create"}


class IntentScorer:
    def __init__(self, agent: Any) -> None:
        self._agent = agent

    def decide(
        self,
        *,
        candidates: list[IntentScore],
        signals: RequestSignals,
        frame: ConversationFrame,
        requested_model: str,
        user_message: str,
        summary: str,
        attachment_metas: list[dict[str, Any]],
        settings: Any,
        force_rules_only: bool = False,
    ) -> tuple[IntentDecision, str]:
        ranked = sorted(candidates, key=lambda item: float(item.score), reverse=True)
        top = ranked[0] if ranked else IntentScore(intent="standard", score=0.0, evidence=["empty_candidates"])
        second = ranked[1] if len(ranked) > 1 else IntentScore(intent="", score=0.0, evidence=[])
        margin = max(0.0, float(top.score) - float(second.score))

        rules_decision = self._build_rules_decision(
            ranked=ranked,
            top=top,
            second=second,
            margin=margin,
            signals=signals,
            frame=frame,
        )

        needs_llm, escalation_reason = self._should_escalate_to_llm(
            ranked=ranked,
            top=top,
            second=second,
            margin=margin,
            signals=signals,
            frame=frame,
            rules_decision=rules_decision,
        )
        if escalation_reason:
            rules_decision = rules_decision.model_copy(update={"escalation_reason": escalation_reason})
        if force_rules_only:
            needs_llm = False
        if not needs_llm:
            return rules_decision, json.dumps(
                {
                    "source": "rules",
                    "top_intent": rules_decision.top_intent,
                    "second_intent": rules_decision.second_intent,
                    "confidence": rules_decision.confidence,
                    "margin": rules_decision.margin,
                    "escalation_reason": rules_decision.escalation_reason,
                },
                ensure_ascii=False,
            )

        llm_decision, raw = self._decide_with_llm(
            rules_decision=rules_decision,
            ranked=ranked,
            signals=signals,
            frame=frame,
            requested_model=requested_model,
            user_message=user_message,
            summary=summary,
            attachment_metas=attachment_metas,
            settings=settings,
        )
        return llm_decision, raw

    def decide_rules_only(
        self,
        *,
        candidates: list[IntentScore],
        signals: RequestSignals,
        frame: ConversationFrame,
    ) -> IntentDecision:
        ranked = sorted(candidates, key=lambda item: float(item.score), reverse=True)
        top = ranked[0] if ranked else IntentScore(intent="standard", score=0.0, evidence=["empty_candidates"])
        second = ranked[1] if len(ranked) > 1 else IntentScore(intent="", score=0.0, evidence=[])
        margin = max(0.0, float(top.score) - float(second.score))
        return self._build_rules_decision(
            ranked=ranked,
            top=top,
            second=second,
            margin=margin,
            signals=signals,
            frame=frame,
        )

    def _build_rules_decision(
        self,
        *,
        ranked: list[IntentScore],
        top: IntentScore,
        second: IntentScore,
        margin: float,
        signals: RequestSignals,
        frame: ConversationFrame,
    ) -> IntentDecision:
        top_intent = str(top.intent or "standard").strip().lower()
        if top_intent not in _ALLOWED_INTENTS:
            top_intent = "standard"
        second_intent = str(second.intent or "").strip().lower()
        if second_intent not in _ALLOWED_INTENTS or float(second.score) <= 0.0:
            second_intent = ""

        requires_tools = bool(
            signals.request_requires_tools
            or signals.attachment_needs_tooling
            or top_intent in {"evidence", "web", "code_lookup"}
            or (top_intent == "generation" and signals.grounded_code_generation_context)
        )
        requires_grounding = bool(
            signals.source_trace_request
            or signals.spec_lookup_request
            or signals.evidence_required
            or (
                signals.grounded_code_generation_context
                and (
                    top_intent == "generation"
                    or (second_intent == "generation" and signals.transform_followup_like)
                )
            )
            or top_intent in {"evidence", "web"}
        )
        requires_web = bool(signals.web_request or top_intent == "web")
        requires_local_lookup = bool(
            signals.local_code_lookup_request
            or signals.default_root_search
            or signals.has_attachments
            or signals.attachment_needs_tooling
        )

        action_type = self._infer_action_type(
            top_intent=top_intent,
            requires_tools=requires_tools,
            grounded_generation=signals.grounded_code_generation_context,
        )
        second_has_signal = float(second.score) > 0.0
        mixed_intent = bool(
            second_has_signal
            and (
                (top_intent == "understanding" and second_intent in {"generation", "meeting_minutes"})
                or ({top_intent, second_intent} == {"understanding", "generation"})
                or ({top_intent, second_intent} == {"understanding", "meeting_minutes"})
                or ({top_intent, second_intent} == {"evidence", "generation"})
                or (
                    {top_intent, second_intent} == {"code_lookup", "generation"}
                    and bool(signals.transform_followup_like)
                )
            )
        )
        confidence = max(0.0, min(1.0, float(top.score)))
        text_value = str(signals.text or "").strip()
        very_short_ambiguous = bool(
            (
                len(text_value) <= 6
                or (signals.reference_followup_like and len(text_value) <= 16)
            )
            and str(signals.inherited_primary_intent or frame.dominant_intent or "").strip().lower() in {"", "standard"}
            and not any(
                (
                    signals.understanding_request,
                    signals.source_trace_request,
                    signals.spec_lookup_request,
                    signals.web_request,
                    signals.local_code_lookup_request,
                    signals.meeting_minutes_request,
                )
            )
        )
        has_nonstandard_inheritance = str(signals.inherited_primary_intent or frame.dominant_intent or "").strip().lower() not in {
            "",
            "standard",
        }
        requires_clarifying_route = bool(
            confidence < INTENT_LOW_CONFIDENCE_THRESHOLD
            and not has_nonstandard_inheritance
            and (
                float(signals.ambiguity_score) >= INTENT_HIGH_AMBIGUITY_THRESHOLD
                or very_short_ambiguous
            )
        )

        reason_short = f"rules_top={top_intent}, margin={margin:.2f}, ambiguity={float(signals.ambiguity_score):.2f}"
        inherited = str(signals.inherited_primary_intent or "").strip().lower()
        if not inherited and (signals.context_dependent_followup or signals.inline_followup_context):
            inherited = str(frame.dominant_intent or "").strip().lower()
        if inherited == "standard":
            inherited = ""

        return IntentDecision(
            candidates=ranked,
            top_intent=top_intent,
            second_intent=second_intent,
            confidence=confidence,
            margin=max(0.0, min(1.0, margin)),
            mixed_intent=mixed_intent,
            requires_clarifying_route=requires_clarifying_route,
            inherited_from_state=inherited,
            requires_tools=requires_tools,
            requires_grounding=requires_grounding,
            requires_web=requires_web,
            requires_local_lookup=requires_local_lookup,
            action_type=action_type,
            reason_short=reason_short,
            source="rules",
            escalation_reason="",
        )

    def _decide_with_llm(
        self,
        *,
        rules_decision: IntentDecision,
        ranked: list[IntentScore],
        signals: RequestSignals,
        frame: ConversationFrame,
        requested_model: str,
        user_message: str,
        summary: str,
        attachment_metas: list[dict[str, Any]],
        settings: Any,
    ) -> tuple[IntentDecision, str]:
        auth_summary = self._agent._auth_manager.auth_summary()
        if not bool(auth_summary.get("available")):
            fallback = rules_decision.model_copy(update={"escalation_reason": "llm_unavailable"})
            return fallback, json.dumps({"skipped": auth_summary.get("reason") or "openai_auth_missing"}, ensure_ascii=False)

        scorer_input = {
            "user_message": str(user_message or "").strip(),
            "history_summary": str(summary or "").strip(),
            "attachments": self._agent._summarize_attachment_metas_for_agents(attachment_metas),
            "enable_tools": bool(getattr(settings, "enable_tools", False)),
            "signals": signals.to_dict(),
            "frame": frame.model_dump(),
            "candidates": [item.model_dump() for item in ranked[:7]],
            "rules_decision": rules_decision.model_dump(),
        }
        messages = [
            self._agent._SystemMessage(
                content=(
                    "你是 Intent Scorer。"
                    "请只输出 JSON，不要输出解释。"
                    "字段固定为 top_intent, second_intent, confidence, mixed_intent, "
                    "requires_tools, requires_grounding, requires_web, requires_local_lookup, "
                    "action_type, reason_short。"
                    "top_intent/second_intent 只能从候选 intent 中选择。"
                    "confidence 范围 0~1。"
                )
            ),
            self._agent._HumanMessage(content=json.dumps(scorer_input, ensure_ascii=False)),
        ]
        try:
            ai_msg, _, effective_model, notes = self._agent._invoke_chat_with_runner(
                messages=messages,
                model=self._agent.config.summary_model or requested_model,
                max_output_tokens=500,
                enable_tools=False,
            )
            raw_text = self._agent._content_to_text(getattr(ai_msg, "content", "")).strip()
            parsed = self._agent._parse_json_object(raw_text)
            if not parsed:
                fallback = rules_decision.model_copy(
                    update={
                        "source": "rules",
                        "classifier_model": effective_model,
                        "escalation_reason": "intent_scorer_invalid_json",
                    }
                )
                return fallback, raw_text

            top_intent = self._normalize_intent(parsed.get("top_intent"), fallback=rules_decision.top_intent)
            second_intent = self._normalize_intent(parsed.get("second_intent"), fallback=rules_decision.second_intent)
            confidence = self._normalize_score(parsed.get("confidence"), fallback=rules_decision.confidence)
            action_type = self._normalize_action_type(parsed.get("action_type"), fallback=rules_decision.action_type)
            mixed_intent = bool(parsed.get("mixed_intent", rules_decision.mixed_intent))
            if top_intent == "understanding" and second_intent in {"generation", "meeting_minutes"}:
                mixed_intent = True
            if {top_intent, second_intent} in ({"understanding", "generation"}, {"understanding", "meeting_minutes"}):
                mixed_intent = True
            if {top_intent, second_intent} == {"evidence", "generation"}:
                mixed_intent = True

            decided = IntentDecision(
                candidates=ranked,
                top_intent=top_intent,
                second_intent=second_intent,
                confidence=confidence,
                margin=rules_decision.margin,
                mixed_intent=mixed_intent,
                requires_clarifying_route=bool(
                    confidence < INTENT_LOW_CONFIDENCE_THRESHOLD
                    and float(signals.ambiguity_score) >= INTENT_HIGH_AMBIGUITY_THRESHOLD
                ),
                inherited_from_state=rules_decision.inherited_from_state,
                requires_tools=bool(parsed.get("requires_tools", rules_decision.requires_tools)),
                requires_grounding=bool(parsed.get("requires_grounding", rules_decision.requires_grounding)),
                requires_web=bool(parsed.get("requires_web", rules_decision.requires_web)),
                requires_local_lookup=bool(parsed.get("requires_local_lookup", rules_decision.requires_local_lookup)),
                action_type=action_type,
                reason_short=str(parsed.get("reason_short") or rules_decision.reason_short).strip(),
                source="llm",
            classifier_model=str(effective_model or "").strip(),
            escalation_reason=rules_decision.escalation_reason or "llm_escalated",
        )
            if notes:
                extras = self._agent._normalize_string_list(notes, limit=2, item_limit=120)
                if extras:
                    decided.reason_short = "; ".join([decided.reason_short, *extras]).strip("; ")
            return decided, raw_text
        except Exception as exc:
            fallback = rules_decision.model_copy(
                update={
                    "source": "rules",
                    "escalation_reason": f"intent_scorer_failed:{str(exc)}",
                }
            )
            return fallback, json.dumps({"error": str(exc)}, ensure_ascii=False)

    def _normalize_intent(self, value: Any, *, fallback: str) -> str:
        normalized = str(value or fallback).strip().lower()
        if normalized not in _ALLOWED_INTENTS:
            return str(fallback or "standard").strip().lower() or "standard"
        return normalized

    def _normalize_action_type(self, value: Any, *, fallback: str) -> str:
        normalized = str(value or fallback).strip().lower()
        if normalized not in _ALLOWED_ACTION_TYPES:
            return str(fallback or "answer").strip().lower() or "answer"
        return normalized

    def _normalize_score(self, value: Any, *, fallback: float) -> float:
        try:
            score = float(value)
        except Exception:
            score = float(fallback)
        return max(0.0, min(1.0, score))

    def _should_escalate_to_llm(
        self,
        *,
        ranked: list[IntentScore],
        top: IntentScore,
        second: IntentScore,
        margin: float,
        signals: RequestSignals,
        frame: ConversationFrame,
        rules_decision: IntentDecision,
    ) -> tuple[bool, str]:
        intents = {str(top.intent or "").strip().lower(), str(second.intent or "").strip().lower()}
        if margin < INTENT_MARGIN_MIXED_THRESHOLD:
            return True, "small_margin"
        if float(signals.ambiguity_score) >= INTENT_HIGH_AMBIGUITY_THRESHOLD:
            return True, "high_ambiguity"
        if signals.transform_followup_like and signals.reference_followup_like:
            return True, "followup_transform_competition"
        if frame.pending_transform == "rewrite_or_transform":
            return True, "followup_pending_transform"
        if signals.short_followup_like and str(rules_decision.inherited_from_state or "").strip():
            return True, "short_followup_inherited_intent"
        if signals.grounded_code_generation_context and intents == {"code_lookup", "generation"}:
            return True, "grounded_generation_code_lookup_competition"
        if signals.grounded_code_generation_context and intents == {"evidence", "generation"}:
            return True, "grounded_generation_evidence_competition"
        if signals.request_requires_tools and rules_decision.top_intent == "standard":
            return True, "tools_required_but_standard"
        if ranked and float(top.score) < INTENT_MARGIN_MIXED_THRESHOLD:
            return True, "low_rules_signal"
        return False, ""

    def _infer_action_type(self, *, top_intent: str, requires_tools: bool, grounded_generation: bool) -> str:
        if top_intent in {"evidence", "web"}:
            return "search"
        if top_intent == "code_lookup":
            return "read"
        if top_intent == "generation":
            return "modify" if grounded_generation or requires_tools else "create"
        if top_intent in {"understanding", "meeting_minutes", "qa"}:
            return "answer"
        return "search" if requires_tools else "answer"
