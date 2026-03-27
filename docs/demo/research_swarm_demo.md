# Research Swarm Demo

## Purpose

This is the first `M5` Swarm MVP demo.

It proves one bounded branch/join flow without rewriting `KernelHost`:

```text
KernelHost.dispatch
  -> research_module.handle
  -> parallel research branches
  -> serial replay for failed branch
  -> Aggregator (merge / deduplicate / mark conflicts)
  -> TaskResponse + trace
```

## Command

```bash
python scripts/demo_research_swarm.py --check
```

Run without `--check` if you want the readable console demo.

## Expected Result

A successful run reports:

- `module_id: research_module`
- `branch_count: 3`
- `degradation.degraded: true`
- at least one `serial_replay` event
- at least one marked conflict
- trace stages for `swarm_branch_plan`, `swarm_degradation`, and `swarm_join`

## Why This Matters

This is the first Swarm path that a non-developer can follow end to end:

- what got split into branches
- what each branch produced
- how the join step merged the results
- how branch failure degraded safely without pushing orchestration into the kernel
