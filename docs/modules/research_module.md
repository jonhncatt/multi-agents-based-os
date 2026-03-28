# Research Module

`research_module` is the second formal business-module candidate and the current default recommendation for the first non-office module to formalize.

## Goal

Provide a clean research-oriented module that can:

- accept a focused investigation query
- gather sources through formal tool/provider contracts
- optionally fetch the top source for evidence preview
- return a structured summary without routing through `office_module`
- classify the response as `success`, `degraded`, `insufficient_evidence`, or `failed`

## Formal Entry

- [`app/business_modules/research_module/module.py`](/Users/dalizhou/Desktop/new_validation_agent/app/business_modules/research_module/module.py)
- [`app/business_modules/research_module/manifest.py`](/Users/dalizhou/Desktop/new_validation_agent/app/business_modules/research_module/manifest.py)
- [`app/business_modules/research_module/module.json`](/Users/dalizhou/Desktop/new_validation_agent/app/business_modules/research_module/module.json)

## Current Pipelines

```text
KernelHost.dispatch(TaskRequest)
  -> research_module.handle(...)
  -> tool_runtime_module.execute(web.search)
  -> optional tool_runtime_module.execute(web.fetch)
  -> structured research summary
```

```text
KernelHost.dispatch(TaskRequest)
  -> research_module.handle(...)
  -> parallel research branches
  -> serial replay for failed branch
  -> Aggregator (merge / deduplicate / mark conflicts)
  -> Swarm research summary + trace
```

## Tool Contract Usage

Required tools:

- `web.search`
- `web.fetch`

Optional future tools:

- `file.read`
- `workspace.read`

The module must not call providers directly.

## Independent Demo Requirement

This module is only considered valid as the second formal module if it can be demonstrated independently of `office_module`.

Use:

```bash
python scripts/demo_research_module.py --check
```

That demo runs `research_module` through `KernelHost` using a deterministic provider stub.

## Operating Standard

Operational guidance for result grades, degradation policy, and escalation rules lives in:

- [docs/operations/research_module_operations.md](/Users/dalizhou/Desktop/new_validation_agent/docs/operations/research_module_operations.md)

## Swarm MVP Demo

`M5` extends `research_module` with a bounded module-local Swarm mode.

Use:

```bash
python scripts/demo_research_swarm.py --check
```

This demo proves:

- multiple research inputs can be processed in parallel
- branch failure degrades through `serial_replay`
- the Aggregator only merges, deduplicates, and marks conflicts
- the Swarm payload exposes a business-readable output block with:
  - `overall_summary`
  - `per_branch_evidence`
  - `conflict_and_degradation_notes`
- trace output exposes `swarm_branch_plan`, `swarm_degradation`, and `swarm_join`

Readable demo notes:

- [docs/demo/research_swarm_demo.md](/Users/dalizhou/Desktop/new_validation_agent/docs/demo/research_swarm_demo.md)
