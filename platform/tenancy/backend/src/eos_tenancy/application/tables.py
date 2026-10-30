"""Every table that holds an organisation's rows, found from the database itself so a module needs no export or
purge code of its own: a table takes part as soon as it carries `organisation_id` (module standard rule 11).

Known models (eos_core.rls.tenant_tables, from Base.metadata) give their Table objects, children before parents;
any other table present in the database with an organisation_id column is reflected. Everything here runs under
platform_scope(), which the callers in service.py set."""

from __future__ import annotations

import base64
import datetime as dt
import uuid
from decimal import Decimal
from typing import Any

from eos_core.db import Base
from eos_core.rls import tenant_tables
from sqlalchemy import MetaData, Table, delete, func, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

ORGANISATION_TABLE = "tenancy_organisation"
# Columns whose values are secrets, never data a person has a right to receive: written as "[redacted]".
REDACTED_COLUMNS = frozenset({"password_hash", "password", "token", "secret", "api_key", "client_secret"})
REDACTED = "[redacted]"
# Columns that reference a file in platform/documents, listed in the export's `files` section.
FILE_COLUMN_SUFFIXES = ("document_id", "file_id")


def organisation_tables(db: Session) -> list[Table]:
    """Tables with an organisation_id column, children before parents. Reflected tables (no model loaded in this
    process) come last; they have no known parents here, and the purge retries them until nothing blocks."""
    bind = db.connection()
    inspector = inspect(bind)
    present = {
        name
        for name in inspector.get_table_names()
        if any(c["name"] == "organisation_id" for c in inspector.get_columns(name))
    }
    known = set(tenant_tables())
    ordered = [t for t in reversed(Base.metadata.sorted_tables) if t.name in known and t.name in present]
    extra = MetaData()
    ordered += [Table(name, extra, autoload_with=bind) for name in sorted(present - known)]
    return ordered


def organisation_row_table() -> Table:
    return Base.metadata.tables[ORGANISATION_TABLE]


def json_safe(value: Any) -> Any:
    """A column value as JSON: dates ISO 8601, Decimal as a string (no float rounding), bytes base64, JSON as is."""
    if isinstance(value, dt.datetime | dt.date | dt.time):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, bytes | bytearray | memoryview):
        return base64.b64encode(bytes(value)).decode("ascii")
    if isinstance(value, dict):
        return {k: json_safe(v) for k, v in value.items()}
    if isinstance(value, list | tuple | set):
        return [json_safe(v) for v in value]
    return value


def export_rows(db: Session, table: Table, organisation_id: str) -> list[dict]:
    """Every row of `table` belonging to the organisation, column name -> JSON-safe value, secrets redacted."""
    column = table.c.id if table.name == ORGANISATION_TABLE else table.c.organisation_id
    rows = db.execute(select(table).where(column == organisation_id)).mappings()
    return [
        {k: (REDACTED if k in REDACTED_COLUMNS and v is not None else json_safe(v)) for k, v in r.items()} for r in rows
    ]


def file_references(table_name: str, rows: list[dict]) -> list[dict]:
    """Document references in any column named document_id / file_id (or ending in _document_id / _file_id)."""
    out = []
    for row in rows:
        for column, value in row.items():
            if value and (
                column in FILE_COLUMN_SUFFIXES or column.endswith(tuple(f"_{s}" for s in FILE_COLUMN_SUFFIXES))
            ):
                out.append({"table": table_name, "row_id": row.get("id"), "column": column, "document_id": value})
    return out


def delete_rows(db: Session, tables: list[Table], organisation_id: str) -> dict[str, int]:
    """Delete the organisation's rows from every table, children first. A table a foreign key still blocks is
    retried on the next pass (each attempt is its own savepoint) until every table is empty; deferrable
    constraints on Postgres are deferred to the commit. Returns rows deleted per table."""
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("SET CONSTRAINTS ALL DEFERRED"))
    counts = {t.name: 0 for t in tables}
    remaining = list(tables)
    while remaining:
        blocked = []
        for table in remaining:
            try:
                with db.begin_nested():
                    result = db.execute(delete(table).where(table.c.organisation_id == organisation_id))
                counts[table.name] += result.rowcount
            except IntegrityError:
                blocked.append(table)
        if len(blocked) == len(remaining):
            names = ", ".join(t.name for t in blocked)
            raise RuntimeError(f"foreign keys block deleting the organisation's rows from {names}")
        remaining = blocked
    return counts


def count_rows(db: Session, table: Table, organisation_id: str) -> int:
    column = table.c.id if table.name == ORGANISATION_TABLE else table.c.organisation_id
    return db.scalar(select(func.count()).select_from(table).where(column == organisation_id)) or 0
