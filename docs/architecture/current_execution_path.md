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
- `packages/runtime_core/kernel_host.py`
  - Status: compatibility shim host
  - Why: capability-runtime based debug/health surfaces still depend on it
- `app/request_analysis_support.py`
  - Status: compatibility shim helpers
- `app/router_intent_support.py`
  - Status: compatibility shim helpers
- `app/router_rules.py`
  - Status: compatibility shim constants
- `app/execution_policy.py`
  - Status: compatibility shim lookup table

## Compatibility Shims

- `app.agent.OfficeAgent`
- `packages.runtime_core.kernel_host.KernelHost`
- `app.request_analysis_support`
- `app.router_intent_support`
- `app.router_rules`
- `app.execution_policy`

## Planned Removal Order

1. Move office prompt/runtime logic fully behind `office_module`
2. Stop `office_module` from delegating to `OfficeAgent`
3. Remove direct dependency on `packages/runtime_core/kernel_host.py`
4. Retire helper shims in `app/request_analysis_support.py`, `app/router_intent_support.py`, `app/router_rules.py`, `app/execution_policy.py`
