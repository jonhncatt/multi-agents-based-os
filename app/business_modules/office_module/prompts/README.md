# Office Module Prompts

This directory is reserved for module-scoped prompts.

Current state:
- The live prompt and role logic still resides in `app/agent.py` and `packages/office_modules/*`.
- `app/business_modules/office_module/module.py` is the formal business-module entrypoint.
- Moving prompt assets here is part of the compatibility-shim retirement plan.
