"""Alembic environment for facility-booking. Touches only tables prefixed facility_booking_ and records its
revision in facility_booking_alembic_version, so each module keeps its own chain."""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from eos_facility_booking.infrastructure.models import PREFIX, TABLES
from sqlalchemy import create_engine

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

VERSION_TABLE = f"{PREFIX}alembic_version"
target_metadata = TABLES[0].metadata


def _url() -> str:
    return context.get_x_argument(as_dictionary=True).get("url") or os.environ.get(
        "EOS_DATABASE_URL", "sqlite:///./eos.db"
    )


def _include(obj, name, type_, reflected, compare_to) -> bool:
    return type_ != "table" or ((name or "").startswith(PREFIX) and name != VERSION_TABLE)


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
