"""organisation_name is what a platform service that may not import tenancy reads through the
eos.organisation_directory entry point."""

from __future__ import annotations

import os
import tempfile
import uuid
from importlib import metadata
from pathlib import Path

os.environ.setdefault("EOS_DATABASE_URL", f"sqlite:///{tempfile.mkdtemp()}/tenancy-directory-test.db")
os.environ.setdefault("EOS_DEV_MODE", "true")
os.environ.setdefault("EOS_REPO_ROOT", str(Path(__file__).resolve().parents[4]))

import pytest
from eos_core.db import SessionLocal, init_db
from eos_core.tenant import organisation_scope, platform_scope
from eos_tenancy.application.service import organisation_name
from eos_tenancy.domain.models import Organisation

GROUP = "eos.organisation_directory"


@pytest.fixture(scope="module", autouse=True)
def _tables():
    init_db()


def _organisation(name: str) -> str:
    slug = f"dir-{uuid.uuid4().hex[:8]}"
    with platform_scope(), SessionLocal() as db:
        org = Organisation(name=name, slug=slug, academy_type="music-academy", status="active")
        db.add(org)
        db.commit()
        return org.id


def test_the_name_is_returned_for_a_known_organisation():
    org_id = _organisation("Rooman Conservatory")
    with SessionLocal() as db:
        assert organisation_name(db, org_id) == "Rooman Conservatory"


def test_an_unknown_organisation_is_none_rather_than_an_error():
    with SessionLocal() as db:
        assert organisation_name(db, str(uuid.uuid4())) is None


def test_it_reads_across_tenants_so_a_consumer_in_another_scope_still_resolves_it():
    """The relay puts a consumer in the event's organisation; the lookup must not depend on that scope."""
    org_id = _organisation("Scoped Academy")
    with organisation_scope(str(uuid.uuid4())), SessionLocal() as db:
        assert organisation_name(db, org_id) == "Scoped Academy"


def test_it_is_published_on_the_entry_point_so_other_processes_find_it():
    points = {p.name: p for p in metadata.entry_points(group=GROUP)}
    assert "tenancy" in points, f"{GROUP} is not declared in tenancy's pyproject.toml"
    assert points["tenancy"].load() is organisation_name
