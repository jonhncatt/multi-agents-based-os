# Platform Operations Overview

This is the single operations entry for the current platform state. It does not create a second status system. Every status below is summarized from existing artifacts, eval summaries, metrics, smoke docs, replay samples, and runbooks.

## Current Stage

Current stage: `platform operations and reporting`

Current platform status:

- platform baseline: stable
- office baseline: gate green and baseline smoke green
- research_module: operational and regression-protected
- Swarm MVP: operational, business-readable, and regression-protected
- replay / smoke / eval: unified enough to support release and reporting, but replay sample depth is still intentionally small

## Main Lines Status

| Line | Current status | Latest evidence | Operator entry |
| --- | --- | --- | --- |
| office baseline | stable | office gate `20/20` passed from `artifacts/evals/regression-summary.json` | `docs/operations/quality_gates.md` |
| research_module | operational | research gate `6/6` passed from `artifacts/evals/research-gate-summary.json`; metrics and operations doc are in place | `docs/operations/research_module_operations.md` |
| Swarm MVP | operational | swarm gate `3/3` passed from `artifacts/evals/swarm-gate-summary.json`; business output, runbook, and metrics are in place | `docs/operations/swarm_mvp_operations.md` |

## Gate And Smoke Overview

### Latest Verified Gate Status

| Gate | Current result | Source |
| --- | --- | --- |
| office gate | pass `20/20` | `artifacts/evals/regression-summary.json` |
| research gate | pass `6/6` | `artifacts/evals/research-gate-summary.json` |
| swarm gate | pass `3/3` | `artifacts/evals/swarm-gate-summary.json` |

### Smoke Matrix Summary

| Smoke layer | Current status | Entry | Purpose | Default use |
| --- | --- | --- | --- | --- |
| baseline smoke | verified in current maintained local check set | `python scripts/demo_minimal_agent_os.py --check` | kernel/runtime baseline boot check | CI |
| module smoke | verified in current maintained local check set | `python scripts/demo_research_module.py --check` | research_module end-to-end path | CI |
| swarm smoke | verified in current maintained local check set | `python scripts/demo_research_swarm.py --check` | research Swarm end-to-end path | CI |
| release smoke | release-only entry, not default CI | `/api/kernel/shadow/smoke`, `/api/kernel/shadow/contracts`, `/api/kernel/shadow/replay` | migration/release validation | release prep only |

Smoke layering contract lives in `docs/operations/smoke_matrix.md`.

## Metrics Overview

### Research Module Metrics

Latest snapshot from `artifacts/platform_metrics/latest.json`:

- gate cases: `6`
- average source count: `1.5`
- fetch success rate: `0.8`
- evidence completeness: `complete=2`, `partial=1`, `insufficient=3`
- degraded response count: `2`
- empty result count: `1`
- conflict detected count: `1`
- result grades: `success=1`, `degraded=2`, `insufficient_evidence=3`

Interpretation:

- the module is operational, but the current gate set still intentionally exercises weak-evidence and degraded scenarios
- empty and insufficient outcomes are visible instead of hidden

### Swarm Metrics

Latest snapshot from `artifacts/platform_metrics/latest.json`:

- gate cases: `3`
- business output present count: `3`
- average branch count: `3.0`
- merged finding count: `avg=2.667`, `min=2`, `max=3`
- degraded run count: `2`
- failed branch count: `0`
- conflict detected count: `1`
- result grades: `success=1`, `degraded=1`, `insufficient_evidence=1`
- return strategies: `deliver_swarm_summary=1`, `return_swarm_summary_with_caveat=1`, `report_swarm_unreliable_and_offer_refine_or_escalate=1`

Interpretation:

- Swarm is not only passing clean runs; it is also exercising degraded and conflict-marked outcomes under gate coverage
- `business_output_present_count == gate_case_count` means the business-facing Swarm contract is intact for every gated case

## Replay Sample Library Overview

Replay sample library root: `evals/replay_samples/`

| Baseline type | Sample count | Current samples |
| --- | --- | --- |
| office | `1` | `office_attachment_followup.json` |
| research | `2` | `research_normal_top_fetch.json`, `research_fetch_failure.json` |
| swarm | `2` | `swarm_fanout_merge.json`, `swarm_serial_replay_conflict.json` |

Use the replay sample library when:

- promoting a stable scenario into a future gate suite
- seeding release regression without inventing a new input format
- explaining representative office / research / Swarm baselines to non-developers

Library contract lives in `evals/replay_samples/README.md`.

## Entry Index

### Demo Entrypoints

- baseline demo: `python scripts/demo_minimal_agent_os.py --check`
- research demo: `python scripts/demo_research_module.py --check`
- swarm demo: `python scripts/demo_research_swarm.py --check`

### Gate Entrypoints

- office gate: `python scripts/run_evals.py --cases evals/gate_cases.json --output artifacts/evals/regression-summary.json`
- research gate: `python scripts/run_evals.py --cases evals/research_gate_cases.json --output artifacts/evals/research-gate-summary.json`
- swarm gate: `python scripts/run_evals.py --cases evals/swarm_gate_cases.json --output artifacts/evals/swarm-gate-summary.json`

### Smoke / Replay / Runbook Entrypoints

- smoke matrix: `docs/operations/smoke_matrix.md`
- replay sample library: `evals/replay_samples/README.md`
- research operations: `docs/operations/research_module_operations.md`
- Swarm operations: `docs/operations/swarm_mvp_operations.md`
- Swarm runbook: `docs/operations/swarm_mvp_runbook.md`
- gate policy: `docs/operations/quality_gates.md`
- metrics definitions: `docs/operations/platform_metrics.md`

## Reporting Entry

Use `docs/operations/platform_reporting_template.md` as the fixed reporting template.

That template standardizes:

- current stage
- this round status
- risks
- blockers
- next step

## Source Of Truth

This overview only summarizes these existing sources:

- `artifacts/evals/regression-summary.json`
- `artifacts/evals/research-gate-summary.json`
- `artifacts/evals/swarm-gate-summary.json`
- `artifacts/platform_metrics/latest.json`
- `docs/operations/smoke_matrix.md`
- `evals/replay_samples/README.md`
- `docs/operations/research_module_operations.md`
- `docs/operations/swarm_mvp_operations.md`
- `docs/operations/swarm_mvp_runbook.md`
