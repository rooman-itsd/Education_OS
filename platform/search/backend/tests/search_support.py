"""Helpers shared by the search tests: the three first types as fixtures, an example provider, organisations with real
identity users, and an event stand-in."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

import yaml
from eos_core.security import create_token
from eos_core.tenant import organisation_scope
from eos_identity.application.service import create_user
from eos_search.application.registry import Registry
from eos_search.domain.documents import Caller, build_document, version_of

PREFIX = "/api/v1/search"
FIXTURES = Path(__file__).parent / "fixtures" / "searchable"
NOW = datetime(2026, 11, 5, 12, 0, tzinfo=UTC)

PERSON = "student-information.person"
COURSE = "academic-management.course"
ARTICLE = "knowledge-base.article"
READ_PERSON = "student-information:person:read"
READ_COURSE = "academic-management:course:read"
READ_ARTICLE = "knowledge-base:article:read"
READ_INTERNAL = "knowledge-base:article:read-internal"

# Test-only roles and what they hold; installed over the real catalogue by the `search_grants` fixture.
ROLES = {
    "reg-staff": {READ_PERSON, READ_COURSE},
    "course-reader": {READ_COURSE},
    "kb-public": {READ_ARTICLE},
    "kb-staff": {READ_ARTICLE, READ_INTERNAL},
    "everything": {READ_PERSON, READ_COURSE, READ_ARTICLE, READ_INTERNAL},
}


def declaration(module: str) -> dict:
    return yaml.safe_load((FIXTURES / f"{module}.yaml").read_text())


@dataclass
class ExampleProvider:
    """What a module's provider looks like (docs: README, "What each first module must add"). Records live in
    memory, keyed by organisation and type, and are returned as plain mappings."""

    module: str
    declaration: dict
    records: dict[tuple[str, str], dict[str, dict]] = field(default_factory=dict)
    calls: list[tuple[str, str, str]] = field(default_factory=list)
    fail: Exception | None = None
    failures_left: int = 0

    def put(self, org: str, type_name: str, record_id: str, **doc) -> None:
        self.records.setdefault((org, type_name), {})[record_id] = {"record_id": record_id, **doc}

    def remove(self, organisation_id: str, type_name: str, record_id: str) -> None:
        self.records.get((organisation_id, type_name), {}).pop(record_id, None)

    def get_document(self, organisation_id: str, type: str, record_id: str):  # noqa: A002
        self.calls.append((organisation_id, type, record_id))
        if self.fail is not None and self.failures_left != 0:
            self.failures_left -= 1
            raise self.fail
        return self.records.get((organisation_id, type), {}).get(record_id)

    def iter_documents(self, organisation_id: str, type: str, after_id: str | None, limit: int):  # noqa: A002
        rows = sorted(self.records.get((organisation_id, type), {}).items())
        return [doc for rid, doc in rows if after_id is None or rid > after_id][:limit]


def person(name: str, status: str = "active", programme: str = "BSc", **extra) -> dict:
    return {"fields": {"name": name, "status": status, "programme": programme, **extra}}


def course(title: str, code: str = "CS-101", description: str = "", status: str = "open", **extra) -> dict:
    return {"fields": {"title": title, "code": code, "description": description, "status": status, **extra}}


def article(title: str, body: str = "", internal: bool = False, **extra) -> dict:
    doc = {"fields": {"title": title, "body": body, "slug": title.lower().replace(" ", "-"), **extra}}
    if internal:
        doc["read_any_of"] = [READ_INTERNAL]
    return doc


def providers() -> dict[str, ExampleProvider]:
    return {
        m: ExampleProvider(m, declaration(m)) for m in ("student-information", "academic-management", "knowledge-base")
    }


def registry_of(provs: dict[str, ExampleProvider]) -> Registry:
    registry = Registry()
    for module, provider in provs.items():
        registry.add(module, provider)
    assert not registry.errors, registry.errors
    return registry


def caller(org: str, *grants: str, user: str | None = None, entitled=None) -> Caller:
    return Caller(
        user_id=user or str(uuid.uuid4()),
        organisation_id=org,
        grants=frozenset(grants),
        entitled_modules=frozenset(entitled) if entitled is not None else None,
    )


def new_org() -> str:
    return str(uuid.uuid4())


def index(
    engine, registry: Registry, organisation_id: str, type_key: str, record_id: str, doc: dict, *, at=NOW
) -> None:
    """Index a document the way the indexer would, without events."""
    spec = registry.types[type_key]
    built = build_document(
        spec, organisation_id=organisation_id, record_id=record_id, raw=doc, version=version_of(at), now=at
    )
    engine.ensure_index(spec)
    engine.index_many(organisation_id, spec, [built])


def later(seconds: float, base: datetime = NOW) -> datetime:
    return base + timedelta(seconds=seconds)


@dataclass(frozen=True)
class FakeEvent:
    """The shape of eos_event_bus Event that search reads."""

    name: str
    organisation_id: str | None
    payload: dict
    occurred_at: datetime = NOW
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    version: int = 1
    actor: str | None = None


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class Org:
    """An organisation id with real identity users holding the test roles."""

    def __init__(self, db):
        self.id = new_org()
        with organisation_scope(self.id):
            self.admin = self.user(db, ["org-admin"], "admin")
            self.member = self.user(db, ["member"], "member")
            self.staff = self.user(db, ["reg-staff", "kb-public"], "staff")
            self.kb_staff = self.user(db, ["kb-staff"], "kbstaff")
            self.everything = self.user(db, ["everything"], "all")

    def user(self, db, roles: list[str], label: str = "user"):
        u = create_user(
            db,
            organisation_id=self.id,
            email=f"{label}-{uuid.uuid4().hex[:8]}@example.com",
            name=label,
            password="Secret123!",
            roles=roles,
        )
        db.commit()
        return u

    def headers(self, user) -> dict:
        return auth(create_token(user_id=user.id, organisation_id=self.id, roles=list(user.roles)))


class SuperAdmin:
    def __init__(self, db):
        from eos_core.tenant import platform_scope

        with platform_scope():
            u = create_user(
                db,
                organisation_id=None,
                email=f"root-{uuid.uuid4().hex[:8]}@example.com",
                name="root",
                password="Secret123!",
                roles=["super-admin"],
                is_super_admin=True,
            )
            db.commit()
        self.id = u.id
        self.headers = auth(create_token(user_id=u.id, organisation_id=None, roles=["super-admin"], super_admin=True))
