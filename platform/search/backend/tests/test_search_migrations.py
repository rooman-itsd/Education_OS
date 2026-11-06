"""The Alembic chain: its own version table, own tables only, every table tenant-scoped, and the models match it."""

import os
import subprocess
import sys
from pathlib import Path

import sqlalchemy as sa
from eos_search.domain.models import TABLE_NAMES

DB_DIR = Path(__file__).resolve().parents[2] / "db"


def alembic(url: str, *args: str) -> None:
    env = {**os.environ, "EOS_DATABASE_URL": url}
    subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(DB_DIR / "alembic.ini"), *args],
        check=True,
        cwd=DB_DIR,
        env=env,
        capture_output=True,
    )


def test_upgrade_creates_only_search_tables_and_downgrade_removes_them(tmp_path):
    url = f"sqlite:///{tmp_path}/chain.db"
    alembic(url, "upgrade", "head")
    inspector = sa.inspect(sa.create_engine(url))
    tables = set(inspector.get_table_names())
    assert tables == set(TABLE_NAMES) | {"search_alembic_version"}
    for table in TABLE_NAMES:
        columns = {c["name"]: c for c in inspector.get_columns(table)}
        assert "organisation_id" in columns and columns["organisation_id"]["nullable"] is False
        assert any(ix["column_names"][:1] == ["organisation_id"] for ix in inspector.get_indexes(table))
    alembic(url, "downgrade", "base")
    assert set(sa.inspect(sa.create_engine(url)).get_table_names()) == {"search_alembic_version"}


def test_the_chain_matches_the_models(tmp_path):
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    from eos_core.db import Base

    url = f"sqlite:///{tmp_path}/parity.db"
    alembic(url, "upgrade", "head")
    mine = {t: Base.metadata.tables[t] for t in TABLE_NAMES}
    metadata = sa.MetaData()
    for table in mine.values():
        table.to_metadata(metadata)
    with sa.create_engine(url).connect() as conn:
        diff = compare_metadata(
            MigrationContext.configure(
                conn, opts={"include_object": lambda o, n, t, r, c: t != "table" or n in TABLE_NAMES}
            ),
            metadata,
        )
    assert diff == [], diff


def test_every_table_is_tenant_scoped_in_the_models():
    from eos_core.db import Base

    for name in TABLE_NAMES:
        column = Base.metadata.tables[name].c.organisation_id
        assert column.nullable is False
