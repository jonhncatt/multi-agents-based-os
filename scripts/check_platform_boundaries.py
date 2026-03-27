from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent

PROTECTED_SHIMS = {
    "app/agent.py",
    "packages/runtime_core/kernel_host.py",
}

RETIRED_SHIM_IMPORTS = {
    "app.execution_policy": "packages.office_modules.execution_policy",
    "app.router_rules": "packages.office_modules.router_hints",
    "app.request_analysis_support": "packages.office_modules.request_analysis",
    "app.router_intent_support": "packages.office_modules.intent_support",
}

ACTIVE_SHIM_IMPORT_ALLOWLIST = {
    "app.agent": {
        "app/business_modules/office_module/module.py",
        "app/core/bootstrap.py",
        "packages/office_modules/agent_module.py",
    },
    "packages.runtime_core.kernel_host": {
        "app/bootstrap/assemble.py",
    },
}

LEGACY_HOST_OBJECT_ACCESS_ALLOWLIST = {
    "app/bootstrap/assemble.py",
    "tests/migration/test_compatibility_shims.py",
}

REQUIRED_DOC_UPDATES = {
    "docs/architecture/platform_boundaries.md",
    "docs/migration/compatibility_shim_inventory.md",
    "docs/migration/deprecation_plan.md",
    "docs/migration/shim_retirement_scoreboard.md",
}


def _git(*args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout.strip()


def _ref_exists(ref: str) -> bool:
    if not ref:
        return False
    proc = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", ref],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0


def _resolve_base(candidate: str | None) -> str:
    if candidate and _ref_exists(candidate):
        return candidate
    for ref in ("origin/main", "main", "HEAD~1"):
        if _ref_exists(ref):
            return ref
    raise SystemExit("Unable to resolve a diff base for platform boundary checks.")


def _changed_entries(base: str, head: str) -> list[tuple[str, str]]:
    output = _git("diff", "--name-status", "--find-renames", f"{base}...{head}")
    entries: list[tuple[str, str]] = []
    for raw_line in output.splitlines():
        if not raw_line.strip():
            continue
        parts = raw_line.split("\t")
        status = parts[0]
        path = parts[-1]
        entries.append((status, path))
    return entries


def _working_tree_entries() -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    for args in (
        ("diff", "--name-status", "--find-renames"),
        ("diff", "--cached", "--name-status", "--find-renames"),
    ):
        output = _git(*args)
        for raw_line in output.splitlines():
            if not raw_line.strip():
                continue
            parts = raw_line.split("\t")
            status = parts[0]
            path = parts[-1]
            entries.append((status, path))
    for raw_line in _git("ls-files", "--others", "--exclude-standard").splitlines():
        path = raw_line.strip()
        if path:
            entries.append(("??", path))
    return entries


def _python_sources() -> list[Path]:
    roots = ("app", "packages", "tests", "scripts")
    paths: list[Path] = []
    for root in roots:
        base = REPO_ROOT / root
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            if "__pycache__" in path.parts or "app/data" in str(path):
                continue
            paths.append(path)
    return paths


def _imports_module(text: str, module_path: str) -> bool:
    escaped = re.escape(module_path)
    patterns = (
        rf"(?m)^\s*from\s+{escaped}\s+import\s+",
        rf"(?m)^\s*import\s+{escaped}(?:\s|$)",
    )
    return any(re.search(pattern, text) for pattern in patterns)


def _retired_shim_import_violations() -> list[str]:
    violations: list[str] = []
    for path in _python_sources():
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        for retired_import, replacement in RETIRED_SHIM_IMPORTS.items():
            if _imports_module(text, retired_import):
                relative = path.relative_to(REPO_ROOT).as_posix()
                violations.append(f"{relative} imports retired shim {retired_import}; use {replacement}")
    return violations


def _active_shim_import_violations() -> list[str]:
    violations: list[str] = []
    for path in _python_sources():
        relative = path.relative_to(REPO_ROOT).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        for shim_import, allowlist in ACTIVE_SHIM_IMPORT_ALLOWLIST.items():
            if not _imports_module(text, shim_import):
                continue
            if relative not in allowlist:
                violations.append(
                    f"{relative} imports active shim {shim_import}; expand module/kernel boundaries instead of adding new shim dependents"
                )
    return violations


def _legacy_host_object_access_violations() -> list[str]:
    violations: list[str] = []
    for path in _python_sources():
        relative = path.relative_to(REPO_ROOT).as_posix()
        if relative in LEGACY_HOST_OBJECT_ACCESS_ALLOWLIST:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        if re.search(r"\.get_legacy_host\s*\(", text):
            violations.append(
                f"{relative} accesses get_legacy_host(); use explicit legacy facade/helper surface instead of the mixed host object"
            )
    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description="Check platform boundary guardrails.")
    parser.add_argument("--base", default="", help="Git base ref/sha to diff against.")
    parser.add_argument("--head", default="HEAD", help="Git head ref/sha. Defaults to HEAD.")
    args = parser.parse_args()

    base = _resolve_base(args.base or "")
    head = args.head
    changed_map: dict[str, str] = {}
    for status, path in _changed_entries(base, head):
        changed_map[path] = status
    if head == "HEAD":
        for status, path in _working_tree_entries():
            changed_map[path] = status
    changed = sorted((status, path) for path, status in changed_map.items())
    changed_paths = {path for _, path in changed}
    changed_shims = sorted(path for path in changed_paths if path in PROTECTED_SHIMS)

    missing_docs = sorted(doc for doc in REQUIRED_DOC_UPDATES if doc not in changed_paths)

    print(f"[platform-boundaries] base={base} head={head}")
    if not changed:
        print("[platform-boundaries] no changed files in diff range")
        return 0

    if changed_shims:
        print("[platform-boundaries] protected compatibility shims changed:")
        for path in changed_shims:
            print(f"  - {path}")
        if missing_docs:
            print("[platform-boundaries] required docs were not updated:")
            for path in missing_docs:
                print(f"  - {path}")
            print(
                "[platform-boundaries] failing because shim changes must update boundary and retirement docs."
            )
            return 1

    retired_violations = _retired_shim_import_violations()
    if retired_violations:
        print("[platform-boundaries] retired shim imports detected:")
        for item in retired_violations:
            print(f"  - {item}")
        print("[platform-boundaries] failing because retired shims must not re-enter the runtime path.")
        return 1

    active_violations = _active_shim_import_violations()
    if active_violations:
        print("[platform-boundaries] active shim dependency expansion detected:")
        for item in active_violations:
            print(f"  - {item}")
        print("[platform-boundaries] failing because active shim dependents must shrink, not grow.")
        return 1

    legacy_host_violations = _legacy_host_object_access_violations()
    if legacy_host_violations:
        print("[platform-boundaries] whole legacy host access detected outside allowlist:")
        for item in legacy_host_violations:
            print(f"  - {item}")
        print("[platform-boundaries] failing because new runtime code must use explicit legacy facades instead of get_legacy_host().")
        return 1

    print("[platform-boundaries] checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
