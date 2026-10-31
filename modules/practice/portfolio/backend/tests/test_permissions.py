"""Permission enforcement tests for portfolio API."""

from conftest import BASE

MANAGER = "portfolio-manager"
LEARNER = "portfolio-learner"
REVIEWER = "portfolio-reviewer"


def test_permission_gates(client, org):
    _, mgr = org.user(MANAGER)
    _, learner = org.user(LEARNER)
    _, reviewer = org.user(REVIEWER)
    _, unprivileged = org.user("unrelated-role")

    # Learner cannot create item types (needs portfolio:item-type:manage)
    res = client.post(f"{BASE}/item-types", json={"name": "Hacked"}, headers=learner)
    assert res.status_code == 403

    # Unprivileged user cannot read item types or items
    assert client.get(f"{BASE}/item-types", headers=unprivileged).status_code == 403
    assert client.get(f"{BASE}/items", headers=unprivileged).status_code == 403

    # Reviewer cannot create items (needs portfolio:item:write)
    itype = client.post(f"{BASE}/item-types", json={"name": "Type1"}, headers=mgr).json()
    assert client.post(f"{BASE}/items", json={"type_id": itype["id"], "title": "T"}, headers=reviewer).status_code == 403

    # Learner can create item
    item = client.post(f"{BASE}/items", json={"type_id": itype["id"], "title": "My Item"}, headers=learner).json()
    assert item["status"] == "draft"

    # Learner cannot review item
    assert client.post(f"{BASE}/items/{item['id']}/reviews", json={"decision": "approved"}, headers=learner).status_code == 403

