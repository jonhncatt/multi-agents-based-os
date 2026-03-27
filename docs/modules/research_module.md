# Research Module

`research_module` is the second formal business-module candidate and the current default recommendation for the first non-office module to formalize.

## Goal

Provide a clean research-oriented module that can:

- accept a focused investigation query
- gather sources through formal tool/provider contracts
- optionally fetch the top source for evidence preview
- return a structured summary without routing through `office_module`

## Formal Entry

- [`app/business_modules/research_module/module.py`](/Users/dalizhou/Desktop/new_validation_agent/app/business_modules/research_module/module.py)
- [`app/business_modules/research_module/manifest.py`](/Users/dalizhou/Desktop/new_validation_agent/app/business_modules/research_module/manifest.py)
- [`app/business_modules/research_module/module.json`](/Users/dalizhou/Desktop/new_validation_agent/app/business_modules/research_module/module.json)

## Current Pipeline

```text
KernelHost.dispatch(TaskRequest)
  -> research_module.handle(...)
  -> tool_runtime_module.execute(web.search)
  -> optional tool_runtime_module.execute(web.fetch)
  -> structured research summary
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
