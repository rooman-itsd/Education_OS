"""Helpers shared by workflow tests."""

from __future__ import annotations

import uuid

from eos_core.security import create_token
from eos_core.tenant import organisation_scope, platform_scope
from eos_identity.application.service import create_user

PREFIX = "/api/v1/workflow"


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
    def __init__(self, db):
        self.id = str(uuid.uuid4())
        with organisation_scope(self.id):
            self.admin = _user(db, self.id, ["org-admin"], "admin")
            self.dept_admin = _user(db, self.id, ["department-admin"], "dept-admin")
            self.faculty = _user(db, self.id, ["faculty"], "faculty")
            self.student = _user(db, self.id, ["student"], "student")
            self.member = _user(db, self.id, ["member"], "member")

    def headers(self, user, *, impersonated_by: str | None = None) -> dict:
        return auth(
            create_token(
                user_id=user.id,
                organisation_id=self.id,
                roles=list(user.roles),
                impersonated_by=impersonated_by,
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


def sample_chain(code: str = "leave_approval") -> dict:
    return {
        "code": code,
        "title": "Leave Approval Process",
        "description": "Two-step approval: HoD then Org Admin",
        "steps": [
            {
                "step_order": 1,
                "name": "HoD Review",
                "approver_role": "department-admin",
                "sla_hours": 24,
                "is_final": False,
            },
            {
                "step_order": 2,
                "name": "Director Sign-off",
                "approver_role": "org-admin",
                "sla_hours": 48,
                "is_final": True,
            },
        ],
    }
