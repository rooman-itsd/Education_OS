"""The searchable types that are installed: each module's declaration plus its document provider.

A module registers a provider on the `eos.search_documents` entry-point group, under its own name:

    [project.entry-points."eos.search_documents"]
    knowledge-base = "eos_knowledge_base.search:PROVIDER"

The loaded object has `declaration` (the parsed contracts/searchable.yaml as a mapping, or a path to the file),
`get_document(organisation_id, type, record_id)` and `iter_documents(organisation_id, type, after_id, limit)`
(application/ports.py). Search validates the declaration here, once, and refuses what does not pass."""

from __future__ import annotations

import logging
from collections.abc import Iterable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from importlib import metadata
from pathlib import Path

import yaml

from ..domain.declarations import TypeSpec, parse_declaration
from ..domain.documents import Caller
from ..domain.errors import DeclarationError

GROUP = "eos.search_documents"
log = logging.getLogger("eos.search")


@dataclass
class Registry:
    types: dict[str, TypeSpec] = field(default_factory=dict)
    providers: dict[str, object] = field(default_factory=dict)  # module -> provider
    errors: list[str] = field(default_factory=list)  # one line per refused type or declaration, no content

    def add(self, module: str, provider: object) -> None:
        """Validate and register one module. A bad type is refused and noted; a bad header refuses the module."""
        try:
            declared_module, specs, refused = parse_declaration(_declaration_of(provider))
            if declared_module != module:
                raise DeclarationError(f"declaration names module {declared_module}, registered as {module}")
            for need in ("get_document", "iter_documents"):
                if not callable(getattr(provider, need, None)):
                    raise DeclarationError(f"{module}: provider has no {need}()")
        except DeclarationError as e:
            self.errors.append(f"{module}: {e}")
            log.error("search: %s refused: %s", module, e)
            return
        for message in refused:
            self.errors.append(message)
            log.error("search: %s", message)
        self.providers[module] = provider
        for spec in specs:
            self.types[spec.key] = spec

    # --- lookups -----------------------------------------------------------------------------------------------
    def module_types(self, module: str) -> list[TypeSpec]:
        return [s for s in self.types.values() if s.module == module]

    def trigger_events(self) -> set[str]:
        return {t.event for s in self.types.values() for t in s.triggers}

    def triggered_by(self, event_name: str) -> Iterator[tuple[TypeSpec, str, str]]:
        """(type, action, id_field) for every type that names this event as a trigger."""
        for spec in self.types.values():
            for trigger in spec.triggers:
                if trigger.event == event_name:
                    yield spec, trigger.action, trigger.id_field

    def visible_types(
        self, caller: Caller, *, module: str | None = None, holding_permission: bool = False
    ) -> list[TypeSpec]:
        """Types in scope for the caller: the module is entitled to the organisation. With `holding_permission` the
        caller must also hold at least one of the type's read permissions, which is what decides the tabs and
        GET /types. Searching does not require it: a document can name the caller in `read_users` (a student's own
        record), and what the caller may read is decided per document in the engine's filter, never here."""
        out = []
        for spec in self.types.values():
            if module is not None and spec.module != module:
                continue
            if caller.entitled_modules is not None and spec.module not in caller.entitled_modules:
                continue
            if holding_permission and not caller.grants & set(spec.read_any_of):
                continue
            out.append(spec)
        return sorted(out, key=lambda s: s.key)


def _declaration_of(provider: object):
    declaration = getattr(provider, "declaration", None)
    if isinstance(declaration, str | Path):
        try:
            return yaml.safe_load(Path(declaration).read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as e:
            raise DeclarationError(f"cannot read the declaration: {type(e).__name__}") from None
    if isinstance(declaration, Mapping):
        return declaration
    raise DeclarationError("provider.declaration must be a mapping or a path to contracts/searchable.yaml")


def load_registry(providers: Iterable[tuple[str, object]] | None = None) -> Registry:
    registry = Registry()
    found = providers
    if found is None:
        found = [(p.name, p.load()) for p in metadata.entry_points(group=GROUP)]
    for module, provider in found:
        registry.add(module, provider)
    return registry


_current: Registry | None = None


def get_registry() -> Registry:
    global _current
    if _current is None:
        _current = load_registry()
    return _current


@contextmanager
def use_registry(registry: Registry) -> Iterator[Registry]:
    """Install a registry for a block (tests; a host that builds its own)."""
    global _current
    previous = _current
    _current = registry
    try:
        yield registry
    finally:
        _current = previous
