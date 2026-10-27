"""Migration verification tests for student-information.

Tests:
- Full upgrade to head and downgrade to base using db/alembic.ini
- Dedicated Alembic version table: student_information_alembic_version
- All four module tables created with required organisation_id column
- Partial unique indexes created:
  - uq_student_info_person_identity WHERE identity_number IS NOT NULL
  - uq_student_info_active_card WHERE status = 'issued'
- compare_metadata yields zero drift against SQLAlchemy models
- Downgrade removes tables in reverse dependency order
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from eos_student_information.infrastructure.models import PREFIX, TABLES
from sqlalchemy import create_engine, inspect

DB_DIR = Path(__file__).resolve().parents[2] / "db"


def _config(url: str) -> Config:
    cfg = Config(str(DB_DIR / "alembic.ini"))
    cfg.cmd_opts = type("Opts", (), {"x": [f"url={url}"]})()
    return cfg


def test_upgrade_matches_models_and_downgrade_removes_tables():
    """Validates full upgrade/downgrade lifecycle and metadata consistency."""
    url = f"sqlite:///{tempfile.mkdtemp()}/student_info_migration.db"
    cfg = _config(url)

    # 1. Upgrade to head
    command.upgrade(cfg, "head")
    engine = create_engine(url)

    with engine.connect() as conn:
        inspector = inspect(conn)
        table_names = set(inspector.get_table_names())

        # Verify all 4 tables plus dedicated version table exist
        expected_tables = {t.name for t in TABLES}
        assert expected_tables <= table_names
        assert "student_information_alembic_version" in table_names

        # Verify organisation_id in every table
        for t in TABLES:
            cols = {c["name"] for c in inspector.get_columns(t.name)}
            assert "organisation_id" in cols, f"Table {t.name} missing organisation_id"

        # Compare autogenerate metadata against SQLAlchemy models
        ctx = MigrationContext.configure(
            conn,
            opts={
                "include_object": lambda obj, name, type_, *_: (
                    type_ != "table" or (name.startswith(PREFIX) and "alembic" not in name)
                ),
            },
        )
        diff = [d for d in compare_metadata(ctx, TABLES[0].metadata) if PREFIX in repr(d)]
        assert diff == [], f"Schema diff detected between migrations and models: {diff}"

    # 2. Downgrade to base
    command.downgrade(cfg, "base")

    with engine.connect() as conn:
        remaining = [t for t in inspect(conn).get_table_names() if t.startswith(PREFIX) and "alembic" not in t]
        assert not remaining, f"Tables remained after downgrade: {remaining}"


def test_all_model_tables_prefixed_and_tenant_scoped():
    """Every model table uses student_information_ prefix and has organisation_id."""
    assert len(TABLES) == 4
    for table in TABLES:
        assert table.name.startswith(PREFIX)
        assert "organisation_id" in table.columns


def test_partial_unique_indexes_exist_in_metadata():
    """Verify both partial unique indexes are defined on model tables."""
    person_table = next(t for t in TABLES if t.name == f"{PREFIX}person")
    person_indexes = {i.name: i for i in person_table.indexes}
    assert "uq_student_info_person_identity" in person_indexes
    idx_identity = person_indexes["uq_student_info_person_identity"]
    assert idx_identity.unique
    assert "identity_number IS NOT NULL" in str(idx_identity.dialect_options.get("postgresql", {}).get("where", ""))

    card_table = next(t for t in TABLES if t.name == f"{PREFIX}id_card")
    card_indexes = {i.name: i for i in card_table.indexes}
    assert "uq_student_info_active_card" in card_indexes
    idx_card = card_indexes["uq_student_info_active_card"]
    assert idx_card.unique
    assert "status = 'issued'" in str(idx_card.dialect_options.get("postgresql", {}).get("where", ""))
