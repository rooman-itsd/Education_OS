"""Alembic environment for workflow. Touches only workflow's tables and records its revision in
workflow_alembic_version, so each service keeps its own chain on the shared database.
"""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from eos_core.db import Base
from eos_workflow.domain.models import TABLE_NAMES
from sqlalchemy import create_engine

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

TABLES = set(TABLE_NAMES)
VERSION_TABLE = "workflow_alembic_version"
target_metadata = Base.metadata


def _url() -> str:
    return context.get_x_argument(as_dictionary=True).get("url") or os.environ.get(
        "EOS_DATABASE_URL", "sqlite:///./eos.db"
    )


def _include(obj, name, type_, reflected, compare_to) -> bool:
    if type_ == "table":
        return name in TABLES
    table = getattr(obj, "table", None)
    return table is None or table.name in TABLES


def run_migrations_offline() -> None:
    context.configure(
        url=_url(),
        target_metadata=target_metadata,
        version_table=VERSION_TABLE,
        include_object=_include,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_url())
    with engine.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata, version_table=VERSION_TABLE, include_object=_include
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
