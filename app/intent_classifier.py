from __future__ import annotations

from typing import Any

from app.candidate_intents import CandidateIntentGenerator
from app.frame_resolver import FrameResolver
from app.intent_constants import (
    INTENT_HIGH_AMBIGUITY_THRESHOLD,
    INTENT_LLM_ESCALATION_THRESHOLD,
    INTENT_LOW_CONFIDENCE_THRESHOLD,
    INTENT_MARGIN_MIXED_THRESHOLD,
)
from app.intent_schema import ConversationFrame, IntentClassification, IntentDecision, IntentScore, RequestSignals
from app.intent_scorer import IntentScorer


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

_ALLOWED_ACTION_TYPES = {"answer", "search", "read", "modify", "create"}


class IntentClassifier:
    def __init__(self, agent: Any) -> None:
        self._agent = agent
        self._frame_resolver = FrameResolver()
        self._candidate_generator = CandidateIntentGenerator()
        self._scorer = IntentScorer(agent)

    def resolve_frame(
        self,
        *,
        user_message: str,
        route_state: dict[str, Any] | None,
        signals: RequestSignals,
    ) -> ConversationFrame:
        return self._frame_resolver.resolve(
            user_message=user_message,
            route_state=route_state,
            signals=signals,
        )

    def classify_decision(
        self,
        *,
        requested_model: str,
        user_message: str,
        summary: str,
        attachment_metas: list[dict[str, Any]],
        settings: Any,
        route_state: dict[str, Any] | None,
        signals: RequestSignals,
        force_rules_only: bool = False,
    ) -> tuple[IntentDecision, str]:
        frame = self.resolve_frame(
            user_message=user_message,
            route_state=route_state,
            signals=signals,
        )
        candidates = self.generate_candidates(signals=signals, frame=frame)
        decision, raw = self.score_decision(
            candidates=candidates,
            requested_model=requested_model,
            user_message=user_message,
            summary=summary,
            attachment_metas=attachment_metas,
            settings=settings,
            signals=signals,
            frame=frame,
            force_rules_only=force_rules_only,
        )
        decision = self.postprocess_decision(decision=decision, signals=signals)

        return decision, raw

    def postprocess_decision(
        self,
        *,
        decision: IntentDecision,
        signals: RequestSignals,
    ) -> IntentDecision:
        updated = decision
        second_score = 0.0
        for candidate in updated.candidates:
            if str(candidate.intent or "").strip().lower() == str(updated.second_intent or "").strip().lower():
                second_score = float(candidate.score or 0.0)
                break

        if not updated.inherited_from_state and signals.inherited_primary_intent:
            updated.inherited_from_state = str(signals.inherited_primary_intent)
        if (
            second_score > 0.0
            and (
            (updated.top_intent == "understanding" and updated.second_intent in {"generation", "meeting_minutes"})
            or ({str(updated.top_intent), str(updated.second_intent)} in ({"understanding", "generation"}, {"understanding", "meeting_minutes"}))
            )
        ):
            updated.mixed_intent = True
        if not updated.escalation_reason and updated.margin < INTENT_MARGIN_MIXED_THRESHOLD:
            updated.escalation_reason = "small_margin"
        if not updated.escalation_reason and float(signals.ambiguity_score) >= INTENT_HIGH_AMBIGUITY_THRESHOLD:
            updated.escalation_reason = "high_ambiguity"
        if not updated.escalation_reason and updated.confidence < INTENT_LLM_ESCALATION_THRESHOLD:
            updated.escalation_reason = "low_rules_confidence"
        return updated

    def generate_candidates(
        self,
        *,
        signals: RequestSignals,
        frame: ConversationFrame,
    ) -> list[IntentScore]:
        return self._candidate_generator.generate(signals=signals, frame=frame)

    def score_decision(
        self,
        *,
        candidates: list[IntentScore],
        requested_model: str,
        user_message: str,
        summary: str,
        attachment_metas: list[dict[str, Any]],
        settings: Any,
        signals: RequestSignals,
        frame: ConversationFrame,
        force_rules_only: bool = False,
    ) -> tuple[IntentDecision, str]:
        return self._scorer.decide(
            candidates=candidates,
            signals=signals,
            frame=frame,
            requested_model=requested_model,
            user_message=user_message,
            summary=summary,
            attachment_metas=attachment_metas,
            settings=settings,
            force_rules_only=force_rules_only,
        )

    def classify(
        self,
        *,
        requested_model: str,
        user_message: str,
        summary: str,
        attachment_metas: list[dict[str, Any]],
        settings: Any,
        route_state: dict[str, Any] | None,
        signals: RequestSignals,
    ) -> tuple[IntentClassification, str]:
        decision, raw = self.classify_decision(
            requested_model=requested_model,
            user_message=user_message,
            summary=summary,
            attachment_metas=attachment_metas,
            settings=settings,
            route_state=route_state,
            signals=signals,
            force_rules_only=False,
        )
        return self._decision_to_classification(decision=decision, signals=signals), raw

    def classify_rules(
        self,
        *,
        user_message: str,
        attachment_metas: list[dict[str, Any]],
        route_state: dict[str, Any] | None,
        signals: RequestSignals,
    ) -> IntentClassification:
        del attachment_metas
        frame = self.resolve_frame(
            user_message=user_message,
            route_state=route_state,
            signals=signals,
        )
        candidates = self.generate_candidates(signals=signals, frame=frame)
        decision = self._scorer.decide_rules_only(candidates=candidates, signals=signals, frame=frame)
        return self._decision_to_classification(decision=decision, signals=signals)

    def classify_with_llm(
        self,
        *,
        requested_model: str,
        user_message: str,
        summary: str,
        attachment_metas: list[dict[str, Any]],
        settings: Any,
        signals: RequestSignals,
        fallback: IntentClassification,
    ) -> tuple[IntentClassification, str]:
        decision, raw = self.classify_decision(
            requested_model=requested_model,
            user_message=user_message,
            summary=summary,
            attachment_metas=attachment_metas,
            settings=settings,
            route_state=signals.route_state,
            signals=signals,
            force_rules_only=False,
        )
        classified = self._decision_to_classification(decision=decision, signals=signals)
        if str(decision.source or "") != "llm":
            classified = fallback.model_copy(
                update={
                    "primary_intent": classified.primary_intent,
                    "secondary_intents": classified.secondary_intents,
                    "requires_tools": classified.requires_tools,
                    "requires_grounding": classified.requires_grounding,
                    "requires_web": classified.requires_web,
                    "requires_local_lookup": classified.requires_local_lookup,
                    "action_type": classified.action_type,
                    "confidence": classified.confidence,
                    "reason_short": classified.reason_short,
                    "source": classified.source,
                    "classifier_model": classified.classifier_model,
                    "mixed_intent": classified.mixed_intent,
                    "inherited_from_state": classified.inherited_from_state,
                    "escalation_reason": classified.escalation_reason,
                }
            )
        return classified, raw

    def classification_from_route(self, route: dict[str, Any]) -> IntentClassification:
        primary_intent = self._normalize_primary_intent(str(route.get("primary_intent") or ""))
        raw_secondary = route.get("secondary_intents")
        secondary: list[str] = []
        if isinstance(raw_secondary, list):
            for item in raw_secondary:
                text = str(item or "").strip().lower()
                if text and text not in secondary:
                    secondary.append(text)

        action_type = self._normalize_action_type(str(route.get("action_type") or "answer"))
        confidence = self._normalize_score(route.get("intent_confidence", route.get("confidence", 0.0)))

        return IntentClassification(
            primary_intent=primary_intent,  # type: ignore[arg-type]
            secondary_intents=secondary,
            requires_tools=bool(route.get("requires_tools")),
            requires_grounding=bool(route.get("requires_grounding")),
            requires_web=bool(route.get("requires_web")),
            requires_local_lookup=bool(route.get("requires_local_lookup")),
            action_type=action_type,  # type: ignore[arg-type]
            confidence=confidence,
            reason_short=str(route.get("intent_reason") or route.get("reason") or "").strip(),
            source=str(route.get("intent_source") or route.get("source") or "rules").strip() or "rules",
            classifier_model=str(route.get("router_model") or "").strip(),
            mixed_intent=bool(route.get("mixed_intent")),
            inherited_from_state=str(route.get("inherited_from_state") or "").strip(),
            escalation_reason=str(route.get("escalation_reason") or "").strip(),
        )

    def _decision_to_classification(
        self,
        *,
        decision: IntentDecision,
        signals: RequestSignals,
    ) -> IntentClassification:
        primary_intent = self._normalize_primary_intent(decision.top_intent)
        secondary: list[str] = []
        if decision.second_intent and decision.second_intent != primary_intent:
            secondary.append(str(decision.second_intent).strip().lower())
        for candidate in decision.candidates[2:6]:
            item = str(candidate.intent or "").strip().lower()
            if item and item != primary_intent and item not in secondary and float(candidate.score) > 0.0:
                secondary.append(item)

        confidence = self._normalize_score(decision.confidence)
        requires_clarifying = bool(
            decision.requires_clarifying_route
            or (confidence < INTENT_LOW_CONFIDENCE_THRESHOLD and float(signals.ambiguity_score) >= INTENT_HIGH_AMBIGUITY_THRESHOLD)
        )
        if requires_clarifying and primary_intent != "standard":
            primary_intent = "standard"

        return IntentClassification(
            primary_intent=primary_intent,  # type: ignore[arg-type]
            secondary_intents=secondary,
            requires_tools=bool(decision.requires_tools),
            requires_grounding=bool(decision.requires_grounding),
            requires_web=bool(decision.requires_web),
            requires_local_lookup=bool(decision.requires_local_lookup),
            action_type=self._normalize_action_type(decision.action_type),  # type: ignore[arg-type]
            confidence=confidence,
            reason_short=str(decision.reason_short or "").strip(),
            source=str(decision.source or "rules").strip() or "rules",
            classifier_model=str(decision.classifier_model or "").strip(),
            mixed_intent=bool(decision.mixed_intent),
            inherited_from_state=str(decision.inherited_from_state or "").strip(),
            escalation_reason=str(decision.escalation_reason or "").strip(),
        )

    def _normalize_primary_intent(self, value: str) -> str:
        normalized = str(value or "").strip().lower()
        if normalized in _ALLOWED_PRIMARY_INTENTS:
            return normalized
        return "standard"

    def _normalize_action_type(self, value: str) -> str:
        normalized = str(value or "").strip().lower()
        if normalized in _ALLOWED_ACTION_TYPES:
            return normalized
        return "answer"

    def _normalize_score(self, value: Any) -> float:
        try:
            score = float(value)
        except Exception:
            score = 0.0
        return max(0.0, min(1.0, score))
