# Quality Gates

## Policy

This repository treats four layers as gates:

- `tests/`: contract and regression safety
- `evals/`: office baseline, research-module, and Swarm behavior gates
- `docs/operations/smoke_matrix.md`: smoke layering contract
- `evals/replay_samples/`: lightweight replay sample corpus for regression seeding
- `scripts/check_platform_boundaries.py`: compatibility-shim and platform-boundary guard
- `scripts/collect_platform_metrics.py`: baseline milestone metrics artifact
- `.github/workflows/regression-ci.yml`: branch gate on push and pull request

## Commands

Install development dependencies:

```bash
pip install -r requirements-dev.txt
```

Run the full local gate set:

```bash
python scripts/check_platform_boundaries.py --base origin/main
python scripts/collect_platform_metrics.py
pytest -q tests
python scripts/run_evals.py --cases evals/gate_cases.json --output artifacts/evals/regression-summary.json
python scripts/run_evals.py --cases evals/research_gate_cases.json --output artifacts/evals/research-gate-summary.json
python scripts/run_evals.py --cases evals/swarm_gate_cases.json --output artifacts/evals/swarm-gate-summary.json
python scripts/demo_minimal_agent_os.py --check
python scripts/demo_research_module.py --check
python scripts/demo_research_swarm.py --check
```

## When To Run Which Gate

- module contract changes: `pytest -q tests/kernel tests/modules tests/migration`
- office/router behavior changes: `pytest -q tests/router` plus `python scripts/run_evals.py --cases evals/gate_cases.json`
- research-module changes: `python scripts/run_evals.py --cases evals/research_gate_cases.json` plus `python scripts/demo_research_module.py --check`
- Swarm MVP changes: `python scripts/run_evals.py --cases evals/swarm_gate_cases.json` plus `python scripts/demo_research_swarm.py --check`
- tool/provider changes: `pytest -q tests/tool_providers tests/integration`
- packaging or compatibility changes: `pytest -q tests/migration`
- shim changes: `python scripts/check_platform_boundaries.py --base origin/main`
- milestone or platform operations changes: `python scripts/collect_platform_metrics.py`

Use `evals/cases.json` separately when you want the broader exploratory suite.
Use [smoke_matrix.md](/Users/dalizhou/Desktop/new_validation_agent/docs/operations/smoke_matrix.md) to decide whether a smoke belongs in baseline, module, Swarm, or release-only coverage.
Use [evals/replay_samples/README.md](/Users/dalizhou/Desktop/new_validation_agent/evals/replay_samples/README.md) when promoting replayable scenarios into future release gates.
Use [platform_operations_overview.md](/Users/dalizhou/Desktop/new_validation_agent/docs/operations/platform_operations_overview.md) as the single operations entry before drilling into individual docs or artifacts.
Use [platform_reporting_template.md](/Users/dalizhou/Desktop/new_validation_agent/docs/operations/platform_reporting_template.md) when preparing status updates.

## CI Behavior

[`regression-ci.yml`](/Users/dalizhou/Desktop/new_validation_agent/.github/workflows/regression-ci.yml) now checks:

- platform boundary guardrails
- platform metrics artifact
- Python compileability
- frontend script syntax
- full pytest suite
- baseline smoke
- module smoke
- Swarm smoke
- office baseline eval gate
- research-module eval gate
- Swarm eval gate

A change is not considered merged safely unless all of these stay green.
