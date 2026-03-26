from __future__ import annotations

from app.intent_schema import ConversationFrame, IntentDecision, RequestSignals


class RouteVerifier:
    def verify(
        self,
        *,
        decision: IntentDecision,
        route: dict[str, object],
        signals: RequestSignals,
        frame: ConversationFrame,
    ) -> tuple[dict[str, object], list[str]]:
        updated = dict(route or {})
        notes: list[str] = []
        actions: list[str] = []

        if bool(decision.requires_tools) and not bool(updated.get("use_worker_tools")):
            updated["use_worker_tools"] = True
            notes.append("requires_tools=true but use_worker_tools=false; forced enable.")
            actions.append("force_enable_worker_tools")

        if bool(decision.mixed_intent) and not bool(updated.get("use_planner")):
            updated["use_planner"] = True
            notes.append("mixed_intent=true but planner was disabled; forced planner.")
            actions.append("force_enable_planner")

        top_intent = str(decision.top_intent or "").strip().lower()
        specialists = list(updated.get("specialists") or [])
        if top_intent in {"evidence", "code_lookup"} and "file_reader" not in specialists:
            notes.append(f"{top_intent} route missing file_reader specialist.")
        if top_intent == "web" and "researcher" not in specialists:
            notes.append("web route missing researcher specialist.")

        execution_policy = str(updated.get("execution_policy") or "").strip().lower()
        if execution_policy == "grounded_generation_pipeline":
            if not bool(updated.get("use_reviewer")):
                updated["use_reviewer"] = True
                notes.append("grounded generation missing reviewer; forced reviewer.")
                actions.append("force_enable_reviewer")
            if not bool(updated.get("use_revision")):
                updated["use_revision"] = True
                notes.append("grounded generation missing revision; forced revision.")
                actions.append("force_enable_revision")
            if not bool(updated.get("use_conflict_detector")):
                updated["use_conflict_detector"] = True
                notes.append("grounded generation missing conflict detector; forced enable.")
                actions.append("force_enable_conflict_detector")

        inherited_value = str(decision.inherited_from_state or "").strip().lower()
        inherited_transform = bool(
            inherited_value
            and inherited_value != "standard"
            and signals.transform_followup_like
            and signals.reference_followup_like
        )
        if inherited_transform and execution_policy == "standard_safe_pipeline":
            updated["task_type"] = "followup_transform"
            updated["execution_policy"] = "followup_transform_pipeline"
            updated["use_planner"] = True
            updated["reason"] = "verifier_followup_transform_override"
            updated["summary"] = "识别到继承态 follow-up transform，改走 followup transform pipeline。"
            notes.append("inherited followup transform routed as standard; switched to followup transform pipeline.")
            actions.append("reroute_followup_transform")

        updated["route_verified"] = True
        updated["verifier_notes"] = notes
        updated["verifier_actions"] = actions
        updated["frame_dominant_intent"] = str(frame.dominant_intent or updated.get("frame_dominant_intent") or "")
        return updated, notes
