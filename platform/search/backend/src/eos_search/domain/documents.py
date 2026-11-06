"""The document search stores, the caller it is filtered for, and the checks between a provider and the engine.

A provider (a module's own code) returns a plain mapping, never an object of this package, so a module imports
nothing from search (module standard rule 1):

    {"record_id": "<the id it was asked for>",
     "fields": {"<declared field>": value, ...},            # must include the title field
     "read_any_of": ["<declared permission key>", ...],     # optional: narrows the type's default
     "read_users": ["<user id>", ...]}                      # optional: at most 50 ids

Search adds `organisation_id` itself, from the event envelope. A provider that names another organisation is
refused."""

from __future__ import annotations

import math
import re
import unicodedata
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime

from .declarations import FieldSpec, TypeSpec
from .errors import DocumentRejected

MAX_TITLE = 300
MAX_TEXT = 5000
MAX_KEYWORD = 256
MAX_READ_USERS = 50
MAX_RECORD_ID = 128
HIGHLIGHT_OPEN, HIGHLIGHT_CLOSE = "", ""
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


@dataclass(frozen=True)
class Caller:
    """Who is searching. Required by every query; there is no query without one. `grants` is the full set of
    permission keys the caller holds, read once per request. `entitled_modules` is None when the organisation's
    entitlement is not known to search yet (then no module is filtered out here; the per-document permission still
    applies)."""

    user_id: str
    organisation_id: str
    grants: frozenset[str]
    entitled_modules: frozenset[str] | None = None

    def __post_init__(self) -> None:
        if not self.organisation_id or not isinstance(self.organisation_id, str):
            raise ValueError("a search caller needs an organisation")
        if not self.user_id or not isinstance(self.user_id, str):
            raise ValueError("a search caller needs a user")


def clean_text(value: str, maximum: int) -> str:
    """Control characters and the two highlight markers are removed (so stored text can never fake a match
    marker), the rest is Unicode-normalised and cut to `maximum`."""
    return unicodedata.normalize("NFC", _CONTROL.sub(" ", value)).strip()[:maximum]


def document_id(organisation_id: str, type_key: str, record_id: str) -> str:
    return f"{organisation_id}:{type_key}:{record_id}"


def canonical_record_id(value) -> str:
    if isinstance(value, bool) or not isinstance(value, str | int):
        raise DocumentRejected("record_id_invalid")
    text = str(value).strip()
    if not text or len(text) > MAX_RECORD_ID or _CONTROL.search(text):
        raise DocumentRejected("record_id_invalid")
    return text


def coerce(field: FieldSpec, value):
    """The stored form of a provider's value, or None to leave the field out. Raises on a wrong type, so a
    provider bug is a rejected document and not a silently wrong index."""
    if value is None:
        return None
    if field.kind in ("text", "keyword"):
        if isinstance(value, bool) or not isinstance(value, str | int | float):
            raise DocumentRejected("field_type")
        text = clean_text(str(value), MAX_TEXT if field.kind == "text" else MAX_KEYWORD)
        return text or None
    if field.kind == "boolean":
        if not isinstance(value, bool):
            raise DocumentRejected("field_type")
        return value
    if field.kind == "number":
        if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
            raise DocumentRejected("field_type")
        return value
    if field.kind == "date":
        if isinstance(value, datetime):
            return (value if value.tzinfo else value.replace(tzinfo=UTC)).isoformat()
        if isinstance(value, date):
            return value.isoformat()
        if isinstance(value, str):
            try:
                return (
                    datetime.fromisoformat(value).isoformat() if "T" in value else date.fromisoformat(value).isoformat()
                )
            except ValueError:
                raise DocumentRejected("field_type") from None
        raise DocumentRejected("field_type")
    raise DocumentRejected("field_type")


def build_document(
    spec: TypeSpec,
    *,
    organisation_id: str,
    record_id: str,
    raw: Mapping,
    version: int,
    now: datetime,
    reindex_run: str | None = None,
) -> dict:
    """The engine document for a provider's answer. `organisation_id` is the event's, never the provider's."""
    if not isinstance(raw, Mapping):
        raise DocumentRejected("document_not_a_mapping")
    if "organisation_id" in raw and str(raw["organisation_id"]) != organisation_id:
        raise DocumentRejected("organisation_mismatch")
    if str(raw.get("record_id", record_id)) != record_id:
        raise DocumentRejected("record_id_mismatch")
    given = raw.get("fields")
    if not isinstance(given, Mapping):
        raise DocumentRejected("fields_missing")
    values: dict = {}
    for name, field in spec.fields.items():
        value = coerce(field, given.get(name))
        if value is not None:
            values[name] = value
    title_value = values.pop(spec.title_field.name, None)
    if not isinstance(title_value, str) or not title_value:
        raise DocumentRejected("title_missing")
    allowed = set(spec.read_any_of)
    any_of = raw.get("read_any_of", None)
    if any_of is None:
        any_of = list(spec.read_any_of)
    elif not isinstance(any_of, list | tuple) or not all(isinstance(k, str) for k in any_of):
        raise DocumentRejected("read_any_of_invalid")
    elif not set(any_of) <= allowed:
        raise DocumentRejected("read_permission_not_declared")
    users = raw.get("read_users") or []
    if not isinstance(users, list | tuple) or len(users) > MAX_READ_USERS or not all(isinstance(u, str) for u in users):
        raise DocumentRejected("read_users_invalid")
    users = [u for u in dict.fromkeys(users) if u and len(u) <= 64]
    if not any_of and not users:
        # A document nobody may read is not indexed (PRD rule 2); the indexer deletes any earlier version.
        raise DocumentRejected("no_read_permission")
    return {
        "doc_id": document_id(organisation_id, spec.key, record_id),
        "organisation_id": organisation_id,
        "type": spec.key,
        "module": spec.module,
        "record_id": record_id,
        "title": clean_text(title_value, MAX_TITLE),
        "read_any_of": list(dict.fromkeys(any_of)),
        "read_users": users,
        "indexed_at": now.astimezone(UTC).isoformat(),
        "source_version": version,
        "reindex_run": reindex_run,
        "fields": values,
    }


def version_of(moment: datetime) -> int:
    """External version of a write: the event's time in microseconds, so a late older event cannot overwrite a
    newer document."""
    aware = moment if moment.tzinfo else moment.replace(tzinfo=UTC)
    return int(aware.timestamp() * 1_000_000)


def valid_uuid(value: str | None) -> bool:
    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, AttributeError, TypeError):
        return False
