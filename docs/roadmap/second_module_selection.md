# Second Module Selection

This document is the decision record for `M2`.

## Selection Goal

Choose the second formal business module that best proves the platform is reusable beyond `office_module`.

The chosen module must satisfy all of the following:

- dispatch through `KernelHost` without changing kernel main behavior
- use tools/providers only through formal registries
- support an independent demo path
- not rely on `office_module` as fallback explanation
- strengthen, not dilute, the later Swarm MVP

## Current Repository Reality

Current non-office business-module candidates are present only as skeletons:

- [`app/business_modules/research_module/module.py`](/Users/dalizhou/Desktop/new_validation_agent/app/business_modules/research_module/module.py)
- [`app/business_modules/coding_module/module.py`](/Users/dalizhou/Desktop/new_validation_agent/app/business_modules/coding_module/module.py)
- [`app/business_modules/adaptation_module/module.py`](/Users/dalizhou/Desktop/new_validation_agent/app/business_modules/adaptation_module/module.py)

As of the current baseline:

- only `office_module` has module docs
- only `office_module` appears in integration tests
- branch/join primitives exist, but Aggregator contract and degradation strategy are still undefined

## Candidate Comparison

| Candidate | Why It Is Plausible | Why Not First | Platform Proof Strength | Independent Demo Potential | Fit For Later Swarm | Recommendation |
| --- | --- | --- | --- | --- | --- | --- |
| `research_module` | Clear separation from office chat flow; naturally uses `web.search`, `web.fetch`, `file.read`, `workspace.read`; easy to explain as investigation over multiple sources | Needs evidence shaping and result packaging discipline | High | High | High | Recommended |
| `multi_file_analysis_module` | Strong bridge to Swarm because multi-input analysis maps naturally to branch/join and aggregation | Not scaffolded yet; creating it now adds both module-selection and module-definition work | High | High | Very high | Acceptable alternative if we explicitly want to pull Swarm forward |
| `coding_module` | Good product value for repo analysis and patch planning; formal tool contract fit is decent | Too easy to blur into existing office coding assistance paths if scope is not strict | Medium | Medium | Medium | Not first choice |
| `adaptation_module` | Interesting longer-term fit for validate/activate workflows | Weakest short-term demo story; least obvious user-facing value | Medium | Low | Medium | Not first choice |
| `document_translation_module` | Easy to understand; clear user value | Too close to translation flows already living under `office_module`; weak platform proof because it looks like a feature extraction from office | Low | Medium | Medium | Do not choose as second formal module |

## Recommendation

Choose `research_module` as the second formal module.

### Why `research_module`

1. It is meaningfully different from `office_module`.
2. It can be explained to non-developers without borrowing office-specific role language.
3. Its tool dependencies are already compatible with the current Tool/Provider contracts.
4. It creates a clean bridge to the later Swarm MVP:
   - multiple sources
   - parallel evidence gathering
   - aggregation into one conclusion

### Why Not `multi_file_analysis_module` First

It is a strong candidate, but choosing it first would combine two unknowns at once:

- introducing a brand-new business module shape
- defining the first Swarm-adjacent product story

That is a valid move later, but it is a heavier proof step than necessary for `M2`.

## Decision Rules

`research_module` remains the default recommendation unless one of these becomes true:

1. the product priority explicitly shifts toward multi-document parallel analysis as the immediate demo target
2. the Swarm MVP is intentionally pulled forward before the second module is delivered
3. a strict non-overlap scope for `coding_module` is defined and approved

## Required Exit Conditions For M3

The second formal module is not considered delivered unless:

- it can be dispatched directly through `KernelHost`
- it has its own module doc
- it has its own tests and integration coverage
- it can be demonstrated independently
- it does not rely on `office_module` to interpret or recover its response
