# Shim Retirement Scoreboard

## Completed

| Shim | Status | Replacement | Notes |
| --- | --- | --- | --- |
| `app/execution_policy.py` | Retired | `packages/office_modules/execution_policy.py` | Removed from runtime imports and guarded by the platform-boundary check |
| `app/router_rules.py` | Retired | `packages/office_modules/router_hints.py` | Removed from runtime imports and guarded by the platform-boundary check |
| `app/request_analysis_support.py` | Retired | `packages/office_modules/request_analysis.py` | Removed from runtime imports and guarded by the platform-boundary check |
| `app/router_intent_support.py` | Retired | `packages/office_modules/intent_support.py` | Removed from runtime imports and guarded by the platform-boundary check |

## Remaining Active Shims

| Shim | Current Role | Next Retirement Dependency |
| --- | --- | --- |
| `app/agent.py` | Legacy Office runtime shim | `office_module` must stop delegating to `OfficeAgent`; remaining work is the execution path itself, while compatibility-only auth/capability/kernel/evolution/role-lab/runtime-override helpers already live in `packages/office_modules/*` |
| `packages/runtime_core/kernel_host.py` | Legacy capability host shell | Agent OS assembly must stop instantiating the compatibility host; blackboard orchestration has already moved out of the class; all observed `__getattr__` fallback categories are drained, so the next blocker is the class-level retirement path itself: removing mixed-host instantiation and `get_legacy_host()` dependence from runtime assembly |
