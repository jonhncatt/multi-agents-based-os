# Current Execution Path

## Canonical Path

```text
HTTP / UI
  -> app/main.py
  -> app/bootstrap/assemble.py
  -> app/kernel/host.py::KernelHost.dispatch(TaskRequest)
  -> app/business_modules/office_module/module.py::OfficeModule.handle(...)
  -> compatibility OfficeAgent runtime
  -> ToolRegistry / ProviderRegistry / ToolBus
  -> TaskResponse + Kernel trace
```

## Notes

- The external business entry is `KernelHost.dispatch(...)`.
- `office_module` is the only formal business module used by the current chat path.
- `app/main.py` still owns HTTP/session/attachment lifecycle.
- `app/core/*` still owns manifest-based kernel modules for router/policy/attachment/finalizer in the legacy runtime.

## Deprecated Or Compatibility Paths

- `app/agent.py`
  - Status: compatibility shim runtime
  - Why: `office_module` still delegates to `OfficeAgent`

## Retired Compatibility Paths

- `packages/runtime_core/kernel_host.py`
  - Status: retired
  - Replacement: `AgentOSRuntime` explicit legacy facade/helper bindings plus `packages/runtime_core/legacy_host_support.py`
- `app/execution_policy.py`
  - Status: retired
  - Replacement: `packages/office_modules/execution_policy.py`
- `app/router_rules.py`
  - Status: retired
  - Replacement: `packages/office_modules/router_hints.py`
- `app/request_analysis_support.py`
  - Status: retired
  - Replacement: `packages/office_modules/request_analysis.py`
- `app/router_intent_support.py`
  - Status: retired
  - Replacement: `packages/office_modules/intent_support.py`

## Compatibility Shims

- `app.agent.OfficeAgent`

## Planned Removal Order

1. Move office prompt/runtime logic fully behind `office_module`
2. Stop `office_module` from delegating to `OfficeAgent`
