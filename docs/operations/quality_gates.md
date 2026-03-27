# Quality Gates

## Policy

This repository treats three layers as gates:

- `tests/`: contract and regression safety
- `evals/`: behavior checks for routing and role policy
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
python scripts/demo_minimal_agent_os.py --check
```

## When To Run Which Gate

- module contract changes: `pytest -q tests/kernel tests/modules tests/migration`
- router or role behavior changes: `pytest -q tests/router` plus `python scripts/run_evals.py --cases evals/gate_cases.json`
- tool/provider changes: `pytest -q tests/tool_providers tests/integration`
- packaging or compatibility changes: `pytest -q tests/migration`
- shim changes: `python scripts/check_platform_boundaries.py --base origin/main`
- milestone or platform operations changes: `python scripts/collect_platform_metrics.py`

Use `evals/cases.json` separately when you want the broader exploratory suite.

## CI Behavior

[`regression-ci.yml`](/Users/dalizhou/Desktop/new_validation_agent/.github/workflows/regression-ci.yml) now checks:

- platform boundary guardrails
- platform metrics artifact
- Python compileability
- frontend script syntax
- full pytest suite
- minimal demo smoke
- regression eval harness

A change is not considered merged safely unless all of these stay green.
