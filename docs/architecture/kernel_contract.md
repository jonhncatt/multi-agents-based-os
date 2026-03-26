# Kernel Contract

## Responsibility

`KernelHost` is the stable kernel orchestration layer.

It is responsible for:

- loading modules
- resolving a business module for a request
- injecting tool/provider access through registries
- running the selected module in isolation
- collecting health and runtime traces
- falling back or rolling back when a module/provider degrades

It must not own:

- office-specific prompt logic
- Router / Planner / Worker / Reviewer / Revision role prompts
- office-specific heuristics
- business-domain rules

## Lifecycle

Supported lifecycle states for modules:

- `init`
- `ready`
- `degraded`
- `disabled`
- `rollback`

## Health

- Every module must expose `health_check()`.
- Every provider must expose `health_check()`.
- Startup runs a health pass and records status in registry state.
- A failed module invocation degrades the module without crashing the kernel.
- Provider repeated failures can open a simple circuit and force fallback.

## Public Surface

- `load_modules()`
- `resolve_module(request)`
- `inject_tools_and_providers(module)`
- `run_module(module, request, context)`
- `observe_and_record(trace)`
- `fallback_or_rollback(module_id)`
- `dispatch(request, module_id=None)`
