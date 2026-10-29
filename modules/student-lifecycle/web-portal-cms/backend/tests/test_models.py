from __future__ import annotations

import pytest
import yaml
from conftest import CONTRACTS, add_announcement, add_page
from eos_core.db import new_id
from eos_web_portal_cms.infrastructure.models import PREFIX, TABLES
from sqlalchemy.exc import IntegrityError


def schema_properties(name: str) -> set[str]:
    schemas = yaml.safe_load((CONTRACTS / "openapi.yaml").read_text(encoding="utf-8"))["components"]["schemas"]
    return set(schemas[name]["properties"])


def test_every_table_is_prefixed_and_tenant_scoped():
    assert len(TABLES) == 3
    for table in TABLES:
        assert table.name.startswith(PREFIX)
        assert table.c.organisation_id.nullable is False


def test_slug_unique_per_organisation(fresh_db):
    org_a, org_b = new_id(), new_id()
    add_page(fresh_db, org_a, slug="about")
    add_page(fresh_db, org_b, slug="about")
    fresh_db.commit()
    with pytest.raises(IntegrityError):
        add_page(fresh_db, org_a, slug="about")


def test_to_dict_matches_the_contract(fresh_db):
    page = add_page(fresh_db, new_id())
    announcement = add_announcement(fresh_db, new_id())
    fresh_db.commit()
    assert set(page.to_dict()) == schema_properties("Page")
    assert set(announcement.to_dict()) == schema_properties("Announcement") - {"visible"}
    assert page.to_dict()["published_at"].endswith("+00:00")
