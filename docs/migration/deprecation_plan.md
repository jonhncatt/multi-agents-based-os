# Deprecation Plan

## Active Compatibility Layers

- `app/agent.py`
- `packages/runtime_core/kernel_host.py`

## Completed Retirements

- `app/execution_policy.py`
  - Replaced by `packages/office_modules/execution_policy.py`
  - Removed from the runtime import path
  - Protected by the platform-boundary gate so legacy imports fail review
- `app/router_rules.py`
  - Replaced by `packages/office_modules/router_hints.py`
  - Removed from the runtime import path
  - Protected by the platform-boundary gate so legacy imports fail review
- `app/request_analysis_support.py`
  - Replaced by `packages/office_modules/request_analysis.py`
  - Removed from the runtime import path
  - Protected by the platform-boundary gate so legacy imports fail review
- `app/router_intent_support.py`
  - Replaced by `packages/office_modules/intent_support.py`
  - Removed from the runtime import path
  - Protected by the platform-boundary gate so legacy imports fail review

## Deletion Conditions

- `office_module` no longer delegates to `OfficeAgent`
- Agent OS assembly no longer needs capability-runtime host objects for health/debug
- `packages/runtime_core/kernel_host.py` is no longer needed even as a thin shell over `packages/runtime_core/legacy_host_support.py`; `__getattr__` fallback access has been observed and drained, and blackboard orchestration no longer belongs to the class
- `app/agent.py` no longer needs to retain compatibility-only session/debug helpers because they live in module-scoped support packages, including auth/capability/kernel/evolution snapshots, role-lab debug demos, and runtime-override demos
- office routing/policy helpers fully live behind module-scoped packages
- integration tests pass without instantiating compatibility host objects

## KernelHost Class-Level Retirement Entry Conditions

Before `packages/runtime_core/kernel_host.py` can enter class-level retirement work, all of the following must be true:

- host-structure fallback access is drained under a full verification pass:
  - `_role_runtime_controller`
  - `_module_registry`
  - `_lc_tools`
  - `_summarize_turns`
- route-helper fallback access is drained under the same verification pass:
  - `_route_request_by_rules`
  - `_build_session_route_state`
  - `_normalize_route_decision_impl`
- debug/inspection fallback access is drained under the same verification pass:
  - `_debug_kernel_module_snapshot`
  - `_debug_tool_registry_snapshot`
  - `_debug_role_contract_matrix`
  - `_debug_capability_multi_module_snapshot`
  - `_debug_route_runtime_override_attachment_context_requires_tooling`
  - `_debug_route_runtime_override_force_tool_followup`
- the verification pass includes:
  - full `pytest`
  - minimal smoke demo
  - gate evals
  - main-entry runtime checks for `health`, `role-lab`, `sandbox`, and `chat`
- `AgentOSRuntime` runtime code no longer adds new `get_legacy_host()` consumers outside the explicit compatibility allowlist
- blackboard orchestration remains externalized in `packages/runtime_core/legacy_host_support.py`
- the legacy facade still covers:
  - `maybe_compact_session`
  - `health`
  - `role-lab`
  - `sandbox`

Status:

- host-structure fallback access: drained
- route-helper fallback access: drained
- debug/inspection fallback access: drained
- office helper tail fallback access: drained
- current remaining blocker: the compatibility host class is still instantiated and surfaced through legacy assembly/facade paths

## Sequence

1. migrate office runtime internals into `app/business_modules/office_module/*`
2. sever `office_module -> OfficeAgent` delegation
3. observe and shrink `KernelHost.__getattr__` fallback access
4. move blackboard orchestration into `packages/runtime_core/legacy_host_support.py`
5. drain host-structure, route-helper, and debug/inspection fallback categories
6. evaluate and remove remaining class-level host-object dependencies from runtime assembly
7. retire legacy capability host coupling
