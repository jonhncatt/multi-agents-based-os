# Tool Provider Contract

## Tool

A Tool is the stable capability surface exposed to business modules.

Each Tool contract declares:

- `tool_id`
- `input_schema`
- `output_schema`
- `timeout`
- `retry_policy`
- `permission_scope`

Current standard contracts:

- `workspace.read`
- `workspace.write`
- `file.read`
- `code.search`
- `web.search`
- `web.fetch`
- `write.patch`
- `session.lookup`

## Provider

A Provider is a replaceable implementation for one or more Tools.

Each Provider contract declares:

- `provider_id`
- `supported_tools`
- `healthcheck()`
- `timeout_policy`
- `degraded_behavior`

## Why Separate Them

- modules depend on stable capabilities, not concrete adapters
- providers can fail independently
- fallback and degradation policy stay in kernel space
- observability can explain which provider actually served a tool

## Runtime Rules

- modules should go through `ToolRegistry -> ProviderRegistry -> ToolBus`
- repeated provider failures can mark a provider degraded
- degraded or circuit-open providers are skipped from the primary chain
- fallback provider usage is recorded in kernel traces
