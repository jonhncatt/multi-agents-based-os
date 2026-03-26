from __future__ import annotations

from typing import Any

from app.business_modules.office_module.workflow import ROLE_CHAIN


OFFICE_PIPELINE_STAGES: tuple[dict[str, str], ...] = (
    {"role": "router", "stage": "route", "detail": "Resolve intent and minimal execution path."},
    {"role": "planner", "stage": "plan", "detail": "Expand work when planning is required."},
    {"role": "worker", "stage": "execute", "detail": "Use tools and draft the answer."},
    {"role": "reviewer", "stage": "review", "detail": "Check evidence and risk before finalize."},
    {"role": "revision", "stage": "revise", "detail": "Apply reviewer feedback and finalize wording."},
)


def build_office_pipeline_trace(*, active_roles: Any = None, current_role: Any = None) -> list[dict[str, str]]:
    active = {str(item or "").strip() for item in (active_roles or ROLE_CHAIN) if str(item or "").strip()}
    current = str(current_role or "").strip()
    trace: list[dict[str, str]] = []
    for stage in OFFICE_PIPELINE_STAGES:
        role = stage["role"]
        status = "planned"
        if role in active:
            status = "active"
        if current and current == role:
            status = "current"
        trace.append({**stage, "status": status})
    return trace
