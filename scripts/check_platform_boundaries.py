from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent

PROTECTED_SHIMS = {
    "app/agent.py",
    "app/request_analysis_support.py",
    "app/router_intent_support.py",
    "app/router_rules.py",
    "app/execution_policy.py",
    "packages/runtime_core/kernel_host.py",
}

REQUIRED_DOC_UPDATES = {
    "docs/architecture/platform_boundaries.md",
    "docs/migration/compatibility_shim_inventory.md",
    "docs/migration/deprecation_plan.md",
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
    return entries


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

    print("[platform-boundaries] checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
