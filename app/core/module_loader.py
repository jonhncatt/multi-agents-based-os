from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

from app.core.module_manifest import parse_module_ref, read_module_manifest, version_dir_name
from app.core.module_types import ModuleReference, ModuleRuntimeContext


class ModuleLoader:
    def __init__(self, context: ModuleRuntimeContext) -> None:
        self._context = context
        self._cache: dict[str, Any] = {}
        self._ref_cache: dict[str, ModuleReference] = {}

    def resolve_ref(self, ref: str, *, expected_kind: str) -> ModuleReference:
        cached = self._ref_cache.get(ref)
        if cached is not None:
            return cached
        raw_ref = str(ref or "").strip()
        if raw_ref.startswith("path:"):
            module_dir = Path(raw_ref.split(":", 1)[1]).expanduser().resolve()
            manifest_path = module_dir / "manifest.toml"
            module_manifest = read_module_manifest(manifest_path)
            if module_manifest.kind != expected_kind:
                raise RuntimeError(f"Module {ref} kind mismatch: expected {expected_kind}, got {module_manifest.kind}")
            reference = ModuleReference(
                kind=module_manifest.kind,
                module_id=module_manifest.id,
                version=module_manifest.version,
                ref=f"path:{module_dir}",
                path=module_dir,
                entrypoint=module_manifest.entrypoint,
                capabilities=module_manifest.capabilities,
            )
            self._ref_cache[ref] = reference
            self._ref_cache[reference.ref] = reference
            return reference
        module_id, version = parse_module_ref(ref)
        module_dir = self._context.modules_dir / module_id / version_dir_name(version)
        manifest_path = module_dir / "manifest.toml"
        module_manifest = read_module_manifest(manifest_path)
        if module_manifest.kind != expected_kind:
            raise RuntimeError(f"Module {ref} kind mismatch: expected {expected_kind}, got {module_manifest.kind}")
        reference = ModuleReference(
            kind=module_manifest.kind,
            module_id=module_manifest.id,
            version=module_manifest.version,
            ref=f"{module_manifest.id}@{module_manifest.version}",
            path=module_dir,
            entrypoint=module_manifest.entrypoint,
            capabilities=module_manifest.capabilities,
        )
        self._ref_cache[ref] = reference
        self._ref_cache[reference.ref] = reference
        return reference

    def load(self, ref: str, *, expected_kind: str) -> tuple[Any, ModuleReference]:
        reference = self.resolve_ref(ref, expected_kind=expected_kind)
        cached = self._cache.get(reference.ref)
        if cached is not None:
            return cached, reference

        module_file_name, attribute_name = reference.entrypoint.split(":", 1)
        module_path = reference.path / module_file_name
        import_name = f"app_dynamic_{reference.kind}_{reference.module_id}_{reference.version.replace('.', '_')}"
        spec = importlib.util.spec_from_file_location(import_name, module_path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Unable to load module spec for {reference.ref}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        factory = getattr(module, attribute_name, None)
        if factory is None:
            raise RuntimeError(f"Entrypoint not found for {reference.ref}: {reference.entrypoint}")
        instance = factory() if isinstance(factory, type) else factory
        self._cache[reference.ref] = instance
        return instance, reference
