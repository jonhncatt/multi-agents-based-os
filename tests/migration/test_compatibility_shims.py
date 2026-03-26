from __future__ import annotations

from pathlib import Path

import app.execution_policy as execution_policy
import app.request_analysis_support as request_analysis_support
import app.router_intent_support as router_intent_support
import app.router_rules as router_rules
from app.business_modules.office_module.manifest import OFFICE_MODULE_COMPATIBILITY_SHIMS
from packages.runtime_core.kernel_host import KernelHost as LegacyKernelHost


def test_compatibility_shim_markers_exist() -> None:
    assert "Compatibility shim" in (request_analysis_support.__doc__ or "")
    assert "Compatibility shim" in (router_intent_support.__doc__ or "")
    assert "Compatibility shim" in (router_rules.__doc__ or "")
    assert "Compatibility shim" in (execution_policy.__doc__ or "")
    assert OFFICE_MODULE_COMPATIBILITY_SHIMS


def test_legacy_imports_and_placeholder_docs_remain_available() -> None:
    assert hasattr(LegacyKernelHost, "run_chat")
    assert Path("packages/agent-core/README.md").is_file()
    assert Path("packages/office-modules/README.md").is_file()
    assert Path("packages/runtime-core/README.md").is_file()
