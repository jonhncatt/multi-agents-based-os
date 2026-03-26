from __future__ import annotations

from app.contracts import ModuleManifest


OFFICE_MODULE_COMPATIBILITY_SHIMS: tuple[str, ...] = (
    "app.agent.OfficeAgent",
    "app.request_analysis_support",
    "app.router_intent_support",
    "app.router_rules",
    "app.execution_policy",
)


OFFICE_MODULE_MANIFEST = ModuleManifest(
    module_id="office_module",
    module_kind="business",
    version="1.1.0",
    description="Office business module with internal Router/Planner/Worker/Reviewer/Revision workflow.",
    capabilities=["task.chat", "task.office", "task.workflow"],
    required_tools=[
        "workspace.read",
        "file.read",
        "web.search",
        "write.patch",
    ],
    optional_tools=[
        "workspace.write",
        "web.fetch",
        "code.search",
        "session.lookup",
    ],
    required_system_modules=["memory_module", "output_module", "tool_runtime_module", "policy_module"],
    min_kernel_version="1.0.0",
    hot_swappable=True,
    entrypoint="app.business_modules.office_module.module:OfficeModule",
    owner="office-agent-os",
    healthcheck="health_check",
    rollback_strategy="registry_rollback",
    compatibility_level="shim",
)
