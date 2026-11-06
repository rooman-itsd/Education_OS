"""What a module declares in contracts/searchable.yaml, parsed and validated (docs/prd.md, decision 1).

Search validates a declaration when it loads it and refuses a type that has an analyzer outside the closed list, no
field with `role: title`, or no read permission. A refused type is not searchable at all: fail closed."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass

from .errors import DeclarationError

KINDS = ("text", "keyword", "date", "number", "boolean")
ANALYZERS = ("english", "name", "code", "keyword_lower")
ACTIONS = ("upsert", "delete")
FILTERABLE_KINDS = ("keyword", "date", "number", "boolean")
MAX_FIELDS = 30
MAX_TRIGGERS = 20
MAX_READ_PERMISSIONS = 20

MODULE_RE = re.compile(r"^[a-z][a-z0-9-]{1,63}$")
NAME_RE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
FIELD_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
EVENT_RE = re.compile(r"^[a-z][a-z0-9-]*(\.[a-z][a-z0-9_-]*){2,}$")
PERMISSION_RE = re.compile(r"^[a-z][a-z0-9-]*:[a-z][a-z0-9_-]*:[a-z][a-z0-9_-]*$")
TYPE_KEY_RE = re.compile(r"^[a-z][a-z0-9-]{1,63}\.[a-z][a-z0-9-]{0,63}$")


@dataclass(frozen=True)
class FieldSpec:
    name: str
    kind: str
    analyzer: str | None = None
    boost: float = 1.0
    role: str | None = None
    snippet: bool = False
    display: bool = False
    filterable: bool = False


@dataclass(frozen=True)
class Trigger:
    event: str
    action: str
    id_field: str


@dataclass(frozen=True)
class TypeSpec:
    module: str
    name: str
    label: str
    url: str
    triggers: tuple[Trigger, ...]
    fields: Mapping[str, FieldSpec]
    read_any_of: tuple[str, ...]

    @property
    def key(self) -> str:
        return f"{self.module}.{self.name}"

    @property
    def title_field(self) -> FieldSpec:
        return next(f for f in self.fields.values() if f.role == "title")

    @property
    def text_fields(self) -> tuple[FieldSpec, ...]:
        return tuple(f for f in self.fields.values() if f.kind == "text")

    @property
    def snippet_fields(self) -> tuple[FieldSpec, ...]:
        return tuple(f for f in self.fields.values() if f.snippet)

    @property
    def display_fields(self) -> tuple[FieldSpec, ...]:
        return tuple(f for f in self.fields.values() if f.display)

    @property
    def filterable_fields(self) -> tuple[str, ...]:
        return tuple(f.name for f in self.fields.values() if f.filterable)

    @property
    def mapping_hash(self) -> str:
        """Changes exactly when the engine mapping must change (fields, kinds, analyzers), so a new index version
        is built for it. Labels, urls, triggers and permissions do not enter the mapping."""
        shape = [(f.name, f.kind, f.analyzer, f.role == "title") for f in self.fields.values()]
        return hashlib.sha256(json.dumps(sorted(shape)).encode()).hexdigest()[:16]


def _str(value, what: str, *, maximum: int = 200) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise DeclarationError(f"{what} must be a non-empty string of at most {maximum} characters")
    return value.strip()


def _bool(value, what: str) -> bool:
    if value is None:
        return False
    if not isinstance(value, bool):
        raise DeclarationError(f"{what} must be true or false")
    return value


def parse_field(name, raw) -> FieldSpec:
    if not isinstance(name, str) or not FIELD_RE.match(name):
        raise DeclarationError(f"field name {name!r} must match {FIELD_RE.pattern}")
    if not isinstance(raw, Mapping):
        raise DeclarationError(f"field {name} must be a mapping")
    unknown = set(raw) - {"kind", "analyzer", "boost", "role", "snippet", "display", "filterable"}
    if unknown:
        raise DeclarationError(f"field {name} has unknown keys {sorted(unknown)}")
    kind = raw.get("kind")
    if kind not in KINDS:
        raise DeclarationError(f"field {name}: kind must be one of {', '.join(KINDS)}")
    analyzer = raw.get("analyzer")
    if kind == "text":
        analyzer = analyzer or "english"
        if analyzer not in ANALYZERS:
            raise DeclarationError(f"field {name}: analyzer must be one of {', '.join(ANALYZERS)}")
    elif analyzer is not None:
        raise DeclarationError(f"field {name}: only text fields take an analyzer")
    boost = raw.get("boost", 1)
    if isinstance(boost, bool) or not isinstance(boost, int | float) or not (0 < boost <= 10):
        raise DeclarationError(f"field {name}: boost must be a number above 0 and at most 10")
    role = raw.get("role")
    if role not in (None, "title"):
        raise DeclarationError(f"field {name}: role must be title")
    if role == "title" and kind != "text":
        raise DeclarationError(f"field {name}: the title field must be text")
    snippet, display, filterable = (
        _bool(raw.get(k), f"field {name}: {k}") for k in ("snippet", "display", "filterable")
    )
    if snippet and kind != "text":
        raise DeclarationError(f"field {name}: only text fields can be a snippet")
    if filterable and kind not in FILTERABLE_KINDS:
        raise DeclarationError(f"field {name}: a {kind} field cannot be filterable")
    return FieldSpec(name, kind, analyzer, float(boost), role, snippet, display, filterable)


def parse_type(module: str, raw) -> TypeSpec:
    if not isinstance(raw, Mapping):
        raise DeclarationError("a type must be a mapping")
    name = raw.get("name")
    if not isinstance(name, str) or not NAME_RE.match(name):
        raise DeclarationError(f"type name {name!r} must match {NAME_RE.pattern}")
    where = f"type {module}.{name}"
    try:
        label = _str(raw.get("label"), "label", maximum=100)
        url = _str(raw.get("url"), "url", maximum=300)
        if not url.startswith("/") or url.startswith("//") or "{id}" not in url:
            raise DeclarationError("url must be a route starting with / and containing {id}")
        triggers_raw = raw.get("triggers") or []
        if not isinstance(triggers_raw, list) or len(triggers_raw) > MAX_TRIGGERS:
            raise DeclarationError(f"triggers must be a list of at most {MAX_TRIGGERS}")
        triggers: list[Trigger] = []
        for t in triggers_raw:
            if not isinstance(t, Mapping) or set(t) - {"event", "action", "id_field"}:
                raise DeclarationError("a trigger has exactly event, action and id_field")
            event, action, id_field = t.get("event"), t.get("action"), t.get("id_field")
            if not isinstance(event, str) or not EVENT_RE.match(event):
                raise DeclarationError(f"trigger event {event!r} is not an event name")
            if not event.startswith(module + "."):
                # A module may only subscribe search to its own events; otherwise it could make another module's
                # event index (or delete) its own documents.
                raise DeclarationError(f"trigger event {event} does not belong to module {module}")
            if action not in ACTIONS:
                raise DeclarationError(f"trigger action must be one of {', '.join(ACTIONS)}")
            if not isinstance(id_field, str) or not FIELD_RE.match(id_field):
                raise DeclarationError("trigger id_field must be a payload field name")
            if any(x.event == event for x in triggers):
                raise DeclarationError(f"event {event} is listed twice")
            triggers.append(Trigger(event, action, id_field))
        fields_raw = raw.get("fields")
        if not isinstance(fields_raw, Mapping) or not fields_raw or len(fields_raw) > MAX_FIELDS:
            raise DeclarationError(f"fields must be a mapping of 1 to {MAX_FIELDS} fields")
        fields = {n: parse_field(n, f) for n, f in fields_raw.items()}
        if sum(1 for f in fields.values() if f.role == "title") != 1:
            raise DeclarationError("exactly one field must have role: title")
        perms = raw.get("read_permissions")
        any_of = perms.get("any_of") if isinstance(perms, Mapping) else None
        if (
            not isinstance(any_of, list)
            or not any_of
            or len(any_of) > MAX_READ_PERMISSIONS
            or not all(isinstance(p, str) and PERMISSION_RE.match(p) for p in any_of)
            or set(perms) - {"any_of"}
        ):
            raise DeclarationError("read_permissions.any_of must list 1 to 20 permission keys (fail closed)")
    except DeclarationError as e:
        raise DeclarationError(f"{where}: {e}") from None
    return TypeSpec(module, name, label, url, tuple(triggers), fields, tuple(dict.fromkeys(any_of)))


def parse_declaration(data) -> tuple[str, list[TypeSpec], list[str]]:
    """(module, accepted types, one message per refused type). A malformed header raises."""
    if not isinstance(data, Mapping):
        raise DeclarationError("a declaration must be a mapping")
    module = data.get("module")
    if not isinstance(module, str) or not MODULE_RE.match(module):
        raise DeclarationError(f"module {module!r} must match {MODULE_RE.pattern}")
    types_raw = data.get("types")
    if not isinstance(types_raw, list) or not types_raw or len(types_raw) > 20:
        raise DeclarationError(f"{module}: types must be a list of 1 to 20 types")
    accepted: list[TypeSpec] = []
    refused: list[str] = []
    for raw in types_raw:
        try:
            spec = parse_type(module, raw)
        except DeclarationError as e:
            refused.append(str(e))
            continue
        if any(s.name == spec.name for s in accepted):
            refused.append(f"type {module}.{spec.name}: declared twice")
            continue
        accepted.append(spec)
    return module, accepted, refused
