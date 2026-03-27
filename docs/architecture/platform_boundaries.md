# Platform Boundaries

## Canonical Rule

All new business capability must enter the system through `business_modules`.

The kernel is responsible for runtime order and isolation only. Compatibility shims may forward requests, but they are not valid homes for new product logic.

## Allowed Logic Zones

Add or evolve logic in these areas when the intent is platform growth:

- `app/business_modules/`
- `app/system_modules/`
- `app/kernel/`
- `app/contracts/`
- `app/tool_providers/`
- `app/bootstrap/`
- `tests/`
- `evals/`
- `docs/`

## Protected Compatibility Zones

These files exist to preserve legacy behavior and migration continuity. They are not valid places for new business heuristics, module-local prompt logic, or Swarm orchestration.

- `app/agent.py`
- `packages/runtime_core/kernel_host.py`

The preferred pattern for these zones is to push reusable logic into adjacent canonical helpers, leaving the shim file as a thin shell.

For `app/agent.py`, prefer `packages/office_modules/*` helpers for session compaction, auth/capability/kernel/evolution snapshots, role-lab debug demos, runtime-override demos, runtime debug views, and other compatibility-only support code.

For `packages/runtime_core/kernel_host.py`, prefer `packages/runtime_core/legacy_host_support.py` for blackboard orchestration, `__getattr__` fallback observability, and other compatibility-only lifecycle glue. `AgentOSRuntime` should consume explicit legacy facades instead of spreading whole mixed host object access.

The current migration focus for `packages/runtime_core/kernel_host.py` is category-based drain-down:

- host-structure dependencies should use explicit shell methods and facades instead of `__getattr__`
  - `_role_runtime_controller`
  - `_module_registry`
  - `_lc_tools`
  - `_summarize_turns`
- route-helper dependencies should use explicit legacy route-helper aliases instead of `__getattr__`
  - `_route_request_by_rules`
  - `_build_session_route_state`
  - `_normalize_route_decision_impl`
- debug/inspection dependencies should prefer explicit legacy inspection methods instead of `__getattr__`
  - `_debug_kernel_module_snapshot`
  - `_debug_tool_registry_snapshot`
  - `_debug_role_contract_matrix`
  - `_debug_capability_multi_module_snapshot`
  - `_debug_route_runtime_override_attachment_context_requires_tooling`
  - `_debug_route_runtime_override_force_tool_followup`

At the current stage, `KernelHost.__getattr__` should no longer be part of the verified runtime path for host-structure, route-helper, debug/inspection, or office-helper compatibility access. The remaining migration question is no longer "what should stop falling through `__getattr__`", but "when can the mixed host object stop existing at all."

## Retired Compatibility Zones

- `app/router_rules.py`
  - replaced by `packages/office_modules/router_hints.py`
  - must not be reintroduced through runtime imports
- `app/request_analysis_support.py`
  - replaced by `packages/office_modules/request_analysis.py`
  - must not be reintroduced through runtime imports
- `app/router_intent_support.py`
  - replaced by `packages/office_modules/intent_support.py`
  - must not be reintroduced through runtime imports
- `app/execution_policy.py`
  - replaced by `packages/office_modules/execution_policy.py`
  - must not be reintroduced through runtime imports

## Team Rules

1. New business capabilities go into `app/business_modules/*`.
2. `KernelHost` may load, dispatch, isolate, observe, and recover. It must not absorb module-specific product logic.
3. A compatibility shim may translate or forward legacy calls, but it must not become the policy owner for new behavior.
4. The second formal module must be independently demoable. It may not rely on `office_module` as a fallback explainer.
5. The first Swarm MVP must stay outside the kernel rewrite path. It should use existing runtime primitives and define at least one failure degradation strategy.

## Required Documentation When A Shim Changes

Any change to a protected compatibility shim must update:

- `docs/migration/compatibility_shim_inventory.md`
- `docs/migration/deprecation_plan.md`

The update must state:

- why the shim still exists
- who still depends on it
- what would allow it to retire

## Active-Shim Dependency Rule

- Existing active shim dependents are explicitly allowlisted in the boundary gate.
- New files must not start importing `app.agent` or `packages.runtime_core.kernel_host`.
- New runtime code must not start calling `get_legacy_host()` outside the explicit compatibility allowlist.
- If a dependency truly must exist, update the allowlist and the shim inventory in the same change, with a retirement reason.

## Review Questions

Use these questions in PR review:

1. Did this change add business logic outside a module boundary
2. Did this change expand a compatibility shim instead of moving logic behind a module
3. If a shim changed, did the inventory and retirement condition change with it
4. Does the change keep `KernelHost` free of business heuristics
5. If the change touches Swarm, does it preserve a defined degradation path
