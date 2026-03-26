# Office Module

## Responsibility

`office_module` is the formal office business module.

It owns:

- the office request boundary
- the internal role pipeline contract
- module manifest / health / rollback metadata
- declared tool requirements
- compatibility delegation to the legacy `OfficeAgent` runtime

It must not be treated as:

- the kernel
- a top-level system module
- a direct provider caller

## Internal Pipeline

Declared role chain:

- `router`
- `planner`
- `worker`
- `reviewer`
- `revision`

Current runtime note:

- `office_module.handle(...)` is the formal entrypoint
- execution still delegates to `app.agent.OfficeAgent`
- this is intentionally marked as compatibility level `shim`

## Tools And Providers

Required tools:

- `workspace.read`
- `file.read`
- `web.search`
- `write.patch`

Optional tools:

- `workspace.write`
- `web.fetch`
- `code.search`
- `session.lookup`

## Kernel Interaction

- `KernelHost.dispatch(...)` resolves `office_module`
- Kernel injects registry context and provider visibility
- Tool/provider selection is recorded in the kernel trace
