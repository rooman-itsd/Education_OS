"""Helpers shared by the audit tests (kept out of conftest.py so test files can import them)."""

from __future__ import annotations

import uuid

from eos_core.security import create_token
from eos_core.tenant import organisation_scope, platform_scope
from eos_identity.application.service import create_user

PREFIX = "/api/v1/audit"
WRITER_ROLE = "audit-test-writer"


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _user(db, organisation_id, roles, label, *, super_admin=False):
    u = create_user(
        db,
        organisation_id=organisation_id,
        email=f"{label}-{uuid.uuid4().hex[:8]}@example.com",
        name=label,
        password="Secret123!",
        roles=roles,
        is_super_admin=super_admin,
    )
    db.commit()
    return u


class Org:
    """An organisation with real identity users: current_principal looks every caller up."""

    def __init__(self, db):
        self.id = str(uuid.uuid4())
        with organisation_scope(self.id):
            self.admin = _user(db, self.id, ["org-admin"], "admin")
            self.member = _user(db, self.id, ["member"], "member")
            self.writer = _user(db, self.id, [WRITER_ROLE], "writer")

    def headers(self, user, *, impersonated_by: str | None = None) -> dict:
        return auth(
            create_token(
                user_id=user.id, organisation_id=self.id, roles=list(user.roles), impersonated_by=impersonated_by
            )
        )


class SuperAdmin:
    def __init__(self, db):
        with platform_scope():
            self.user = _user(db, None, ["super-admin"], "root", super_admin=True)
        self.id = self.user.id
        self.headers = auth(
            create_token(user_id=self.id, organisation_id=None, roles=["super-admin"], super_admin=True)
        )


def new_record(**overrides) -> dict:
    body = {
        "module": "admissions",
        "action": "application.accepted",
        "entity_type": "application",
        "entity_id": str(uuid.uuid4()),
        "summary": "Application accepted",
        "before": {"status": "submitted"},
        "after": {"status": "accepted"},
    }
    body.update(overrides)
    return body
