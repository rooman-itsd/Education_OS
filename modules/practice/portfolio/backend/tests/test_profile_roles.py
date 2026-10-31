"""Academy profile roles integration tests."""

from conftest import BASE
from eos_core.config import permissions_for

LEARNER_ROLES = [
    "actor",
    "artist",
    "designer",
    "filmmaker",
    "musician",
    "research-scholar",
    "teacher-trainee",
]

REVIEWER_ROLES = [
    "design-mentor",
    "mentor-teacher",
    "music-teacher",
    "research-supervisor",
    "studio-instructor",
]


def test_learner_profile_roles_access(client, org):
    _, mgr = org.user("portfolio-manager")
    itype = client.post(f"{BASE}/item-types", json={"name": "Universal Type"}, headers=mgr).json()

    for role in LEARNER_ROLES:
        _, token = org.user(role)
        # Should be able to list types
        res = client.get(f"{BASE}/item-types", headers=token)
        assert res.status_code == 200, f"{role} failed to read item types"
        # Should be able to create item
        create_res = client.post(
            f"{BASE}/items",
            json={"type_id": itype["id"], "title": f"Work by {role}"},
            headers=token,
        )
        assert create_res.status_code == 201, f"{role} failed to create item: {create_res.text}"


def test_reviewer_profile_roles_access(client, org):
    for role in REVIEWER_ROLES:
        grants = permissions_for([role])
        assert "portfolio:item:read" in grants, f"{role} missing portfolio:item:read"
        assert "portfolio:review:write" in grants, f"{role} missing portfolio:review:write"
