"""Alembic environment for student-information. Touches only tables prefixed student_information_ and
records its revision in student_information_alembic_version, so each module keeps its own chain."""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import MetaData, create_engine

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

_src = str(Path(__file__).resolve().parents[2] / "backend" / "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

try:
    from eos_student_information.infrastructure.models import PREFIX, TABLES

    target_metadata = TABLES[0].metadata
except ImportError:
    PREFIX = "student_information_"
    target_metadata = MetaData()

VERSION_TABLE = f"{PREFIX}alembic_version"


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
