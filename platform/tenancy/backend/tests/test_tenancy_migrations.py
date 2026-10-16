"""The tenancy Alembic chain creates exactly the tables the models describe, and downgrades cleanly."""

import tempfile
from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from eos_core.db import Base
from eos_tenancy.domain.models import Organisation, OrganisationModule, RegistrationToken
from sqlalchemy import create_engine, inspect

DB_DIR = Path(__file__).resolve().parents[2] / "db"
TABLES = {Organisation.__tablename__, RegistrationToken.__tablename__, OrganisationModule.__tablename__}


def _config(url: str) -> Config:
    cfg = Config(str(DB_DIR / "alembic.ini"))
    cfg.cmd_opts = type("Opts", (), {"x": [f"url={url}"]})()
    return cfg


def test_upgrade_matches_models_and_downgrade_removes_tables():
    url = f"sqlite:///{tempfile.mkdtemp()}/tenancy.db"  # a fresh throwaway file, never a real database
    cfg = _config(url)
    command.upgrade(cfg, "head")
    engine = create_engine(url)
    with engine.connect() as conn:
        tables = set(inspect(conn).get_table_names())
        assert TABLES <= tables
        assert "tenancy_alembic_version" in tables
        for t in ("tenancy_registration_token", "tenancy_organisation_module"):
            assert "organisation_id" in {c["name"] for c in inspect(conn).get_columns(t)}
        ctx = MigrationContext.configure(
            conn,
            opts={
                "include_object": lambda obj, name, type_, *_: (
                    (name in TABLES)
                    if type_ == "table"
                    else (getattr(obj, "table", None) is None or obj.table.name in TABLES)
                )
            },
        )
        assert compare_metadata(ctx, Base.metadata) == []
    command.downgrade(cfg, "base")
    with engine.connect() as conn:
        assert not TABLES & set(inspect(conn).get_table_names())
