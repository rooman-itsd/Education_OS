"""Fee heads, fee structures and settings (stories F1, F2, F13)."""

from fees_support import BASE, head, outbox, published, structure_body


def test_fee_heads(client, org):
    h = head(client, org, "TUITION")
    assert h["category"] == "tuition" and h["active"] and h["organisation_id"] == org.id
    dup = client.post(f"{BASE}/fee-heads", json={"code": "TUITION", "name": "Again"}, headers=org.staff)
    assert dup.status_code == 409 and dup.json()["detail"]["code"] == "code_taken"
    r = client.put(
        f"{BASE}/fee-heads/{h['id']}",
        json={"code": "TUITION", "name": "Tuition fee", "active": False},
        headers=org.staff,
    )
    assert r.status_code == 200 and r.json()["name"] == "Tuition fee" and not r.json()["active"]
    active = client.get(f"{BASE}/fee-heads?active=true", headers=org.staff).json()
    assert h["id"] not in {x["id"] for x in active}
    bad = client.post(f"{BASE}/fee-heads", json={"code": "lower", "name": "x"}, headers=org.staff)
    assert bad.status_code == 422


def test_structure_lifecycle(client, org):
    h1, h2 = head(client, org, "TUI1"), head(client, org, "LIB1", "library")
    r = client.post(f"{BASE}/fee-structures", json=structure_body([h1, h2]), headers=org.staff)
    assert r.status_code == 201
    s = r.json()
    assert s["status"] == "draft" and s["total"] == "40000.00" and s["organisation_id"] == org.id
    edited = client.put(f"{BASE}/fee-structures/{s['id']}", json=structure_body([h1], name="Edited"), headers=org.staff)
    assert edited.json()["name"] == "Edited" and edited.json()["total"] == "30000.00"
    pub = client.post(f"{BASE}/fee-structures/{s['id']}/publish", headers=org.staff)
    assert pub.json()["status"] == "published" and pub.json()["published_at"]
    [event] = [e for e in outbox("fees-accounts.fee-structure.published", org.id) if e["fee_structure_id"] == s["id"]]
    assert event["total"] == "30000.00"
    assert (
        client.put(f"{BASE}/fee-structures/{s['id']}", json=structure_body([h1]), headers=org.staff).status_code == 409
    )
    assert client.post(f"{BASE}/fee-structures/{s['id']}/publish", headers=org.staff).status_code == 409
    assert client.post(f"{BASE}/fee-structures/{s['id']}/archive", headers=org.staff).json()["status"] == "archived"
    listed = client.get(f"{BASE}/fee-structures?status=archived", headers=org.staff).json()
    assert s["id"] in {x["id"] for x in listed}


def test_structure_validation(client, org):
    h = head(client, org, "TUI2")
    bad_percent = structure_body([h], instalments=[{"label": "T1", "percent": 90, "due_date": "2026-10-31"}])
    r = client.post(f"{BASE}/fee-structures", json=bad_percent, headers=org.staff)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_instalments"
    unknown = structure_body([{"id": "nope"}])
    assert client.post(f"{BASE}/fee-structures", json=unknown, headers=org.staff).status_code == 422
    late = structure_body([h], late_fee={"kind": "per_day", "amount": "10", "grace_days": 3, "cap": "300"})
    s = client.post(f"{BASE}/fee-structures", json=late, headers=org.staff).json()
    assert s["late_fee"] == {"kind": "per_day", "amount": "10.00", "grace_days": 3, "cap": "300.00"}


def test_hostel_and_transport_selectors(client, org):
    s = published(client, org, room_type="double", name="Hostel double")
    assert s["room_type"] == "double" and s["route_id"] is None


def test_permissions(client, org):
    assert client.get(f"{BASE}/fee-heads").status_code == 401
    assert client.get(f"{BASE}/fee-heads", headers=org.student).status_code == 403
    assert client.get(f"{BASE}/fee-heads", headers=org.manager).status_code == 200
    r = client.post(f"{BASE}/fee-heads", json={"code": "XX", "name": "x"}, headers=org.manager)
    assert r.status_code == 403 and r.json()["detail"]["code"] == "forbidden"


def test_settings(client, org):
    assert client.get(f"{BASE}/settings", headers=org.staff).json() == {
        "invoice_library_fines": False,
        "invoice_staff_transport": False,
    }
    r = client.put(f"{BASE}/settings", json={"invoice_library_fines": True}, headers=org.staff)
    assert r.json() == {"invoice_library_fines": True, "invoice_staff_transport": False}
    assert client.put(f"{BASE}/settings", json={}, headers=org.manager).status_code == 403
