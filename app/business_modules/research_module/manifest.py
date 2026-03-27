from __future__ import annotations

from app.contracts import ModuleManifest


RESEARCH_MODULE_MANIFEST = ModuleManifest(
    module_id="research_module",
    module_kind="business",
    version="0.3.0",
    description="Research business module for focused source gathering, evidence fetching, structured investigation summaries, and a bounded parallel Swarm MVP.",
    capabilities=["task.research", "task.investigation", "task.research.swarm"],
    required_tools=["web.search", "web.fetch"],
    optional_tools=["file.read", "workspace.read"],
    required_system_modules=["memory_module", "output_module", "tool_runtime_module", "policy_module"],
    min_kernel_version="1.0.0",
    hot_swappable=True,
    entrypoint="app.business_modules.research_module.module:ResearchModule",
    owner="research-agent-os",
    healthcheck="health_check",
    rollback_strategy="registry_rollback",
    compatibility_level="native",
)
