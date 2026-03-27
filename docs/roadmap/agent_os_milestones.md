# Agent OS Milestones

This roadmap tracks the next execution phase as milestones instead of calendar weeks.

Execution order is fixed:

`M1 -> M2 -> M3 -> M4 -> M5 -> M6`

Current status:

- `M1` complete
- `M2` complete
- `M3` complete
- `M4` complete
- `M5` complete
- `M6` active

## M1 Platform Boundaries And Baseline Metrics

### Goal

Freeze the platform boundary rules and start collecting the minimum metrics required to manage shim retirement, the second-module track, and Swarm readiness.

### Outputs

- [`docs/architecture/platform_boundaries.md`](/Users/dalizhou/Desktop/new_validation_agent/docs/architecture/platform_boundaries.md)
- [`docs/migration/compatibility_shim_inventory.md`](/Users/dalizhou/Desktop/new_validation_agent/docs/migration/compatibility_shim_inventory.md)
- [`docs/operations/platform_metrics.md`](/Users/dalizhou/Desktop/new_validation_agent/docs/operations/platform_metrics.md)
- [`scripts/check_platform_boundaries.py`](/Users/dalizhou/Desktop/new_validation_agent/scripts/check_platform_boundaries.py)
- [`scripts/collect_platform_metrics.py`](/Users/dalizhou/Desktop/new_validation_agent/scripts/collect_platform_metrics.py)
- workflow boundary gate and metrics artifact upload

### Exit Criteria

- `KernelHost` vs module vs shim boundaries are documented and reviewable.
- Every active shim has:
  - existence reason
  - known dependents
  - retirement condition
- CI blocks at least one invalid behavior:
  - protected shim changed without inventory + deprecation docs update
- Baseline metrics start producing JSON artifacts for:
  - shim inventory
  - second-module readiness baseline
  - Swarm readiness baseline

### Risks

- Boundary rules remain documentation-only and do not affect review behavior.
- Metrics are defined too late and cannot support later milestone exit decisions.

## M2 Second Module Selection

### Goal

Choose the second formal business module and prove why it is the right platform-validation target.

### Outputs

- module charter
- scope and non-goals
- tool/provider dependency plan
- independent demo path
- candidate comparison table

### Candidate Comparison Template

| Candidate | Why It Is Plausible | Why It Should Not Be Chosen First | Platform Proof Strength | Independent Demo Potential | Current Recommendation |
| --- | --- | --- | --- | --- | --- |
| `research_module` | Clear separation from office chat flow; good fit for multi-source investigation | Needs stricter result-shaping and evidence discipline | High | High | Recommended default |
| `multi_file_analysis_module` | Strong bridge to future Swarm MVP; easy to explain to non-developers | Needs new module surface, not yet scaffolded | High | High | Acceptable alternative |
| `coding_module` | Valuable for repo analysis and patch planning | Too close to office coding assistance paths if scoped poorly | Medium | Medium | Not first choice |
| `adaptation_module` | Architecturally interesting for validate/activate workflows | Product story is weaker for early demonstration | Medium | Low | Not first choice |
| `document_translation_module` | Obvious user value | Too close to current office translation task flow; weak proof that platform is general | Low | Medium | Do not choose as second formal module |

### Exit Criteria

- One module is selected with a documented why/why-not decision.
- The chosen module has a direct request path through `KernelHost`.
- The chosen module is explicitly forbidden from relying on `office_module` as fallback explanation.

### Risks

- The second module becomes a disguised feature split of `office_module`.
- Kernel changes are used to compensate for unclear module scope.

## M3 Second Formal Module Delivery

### Goal

Ship the second module as a real business module, not a placeholder skeleton.

### Outputs

- formal module implementation
- manifest + contract coverage
- module docs
- module-specific tests and evals
- independent demo path

### Exit Criteria

- The module dispatches through `KernelHost` without changing kernel main behavior.
- The module uses tools/providers only through formal registries.
- The module is independently demoable.
- The module does not depend on `office_module` fallback behavior.

### Risks

- The module can only run when office compatibility runtime explains or recovers for it.
- Module-local behavior leaks back into kernel or shim layers.

## M4 Swarm Contract Freeze

### Goal

Define the smallest Swarm contract that is worth building without turning it into a kernel rewrite.

### Outputs

- branch/join contract
- Aggregator minimum responsibilities
- trace requirements
- degradation strategy definition

### Aggregator Minimum Responsibilities

- merge
- deduplicate
- mark conflicts

### Required Degradation Strategy

At least one must be chosen and documented:

- failed branch falls back to serial replay
- aggregator conflict is marked and surfaced without forced arbitration

### Exit Criteria

- Branch/join/aggregate I/O contracts are explicit.
- At least one degradation strategy is selected and documented.
- The plan keeps Swarm outside a kernel rewrite path.

### Risks

- Swarm MVP scope expands into a second scheduler.
- Aggregator becomes an over-smart decision owner too early.

## M5 Swarm MVP

### Goal

Deliver one non-trivial Swarm flow that can be demonstrated clearly to non-developers.

### Recommended Scope

- multi-input parallel processing
- minimal aggregation

Recommended first scenario:

- multiple attachments or documents processed in parallel
- one Aggregator produces a unified result

### Outputs

- runnable demo
- branch/join runtime view
- Aggregator output
- regression coverage

### Demo Standard

The MVP is not complete unless a non-developer can understand:

- what got split into branches
- what each branch produced
- how the final output was merged
- what happened when one branch failed

### Exit Criteria

- The flow is runnable and explainable.
- UI or trace clearly shows branch/join stages.
- The chosen degradation strategy is observable in the demo.
- Aggregator only performs minimum responsibilities.

### Risks

- MVP is technically runnable but unreadable outside the engineering team.
- Swarm implementation starts migrating business orchestration into the kernel.

## M6 Gates And Shim Retirement

### Goal

Turn platform intent into merge rules and retire at least one active shim for real.

### Outputs

- module contract gate
- Swarm regression gate
- shim anti-regression gate
- shim retirement scoreboard
- at least one completed shim retirement

### Exit Criteria

- PR and push workflows enforce:
  - module contract safety
  - Swarm regression safety
  - anti-regression checks for protected shims
- At least one shim is formally retired, not just tracked.
- Retirement progress is measurable in metrics artifacts.

### Risks

- Management dashboards exist, but no shim actually leaves the system.
- Gates are present but do not block the most common regression path.

## Standing Constraints

- Do not turn the second module into an `office_module` pseudo-split.
- Do not turn the first Swarm MVP into a new kernel rewrite.
