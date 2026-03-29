# Platform Reporting Template

Use this template for project, operations, or milestone reporting. Keep it short and fill it from the current overview, eval artifacts, metrics, and runbooks.

## Template

### Current Stage

- stage:
- current objective:

### This Round Status

- office baseline:
- research_module:
- Swarm MVP:
- gates:
- smoke:
- replay sample library:

### Risks

- risk 1:
- risk 2:

### Blockers

- blocker 1:
- blocker 2:

### Next Step

- next step 1:
- next step 2:

## Fill Rules

- quote gate counts directly from `artifacts/evals/*.json`
- quote research and Swarm metrics directly from `artifacts/platform_metrics/latest.json`
- use `docs/operations/platform_operations_overview.md` as the default single entry before reading deeper docs
- only call something `green` when the matching gate or smoke entry has actually passed in the current maintained check set
- if a result is `degraded` or `insufficient_evidence`, say so plainly instead of folding it into `success`
