# Package Consolidation

## Canonical Packages

Canonical import packages are snake_case:

- `packages/agent_core`
- `packages/office_modules`
- `packages/runtime_core`

## Placeholder Distribution Directories

Hyphenated directories remain only as compatibility/documentation placeholders:

- `packages/agent-core`
- `packages/office-modules`
- `packages/runtime-core`

These directories do not hold the canonical Python implementation.

## Current Rule

- Python import path: use snake_case packages only
- Distribution / historical naming: document via hyphenated placeholder directory only

## Removal Plan

1. keep placeholder README while external references still mention hyphenated names
2. update packaging/build scripts to point only at snake_case implementations
3. remove placeholder directories when no external references require them
