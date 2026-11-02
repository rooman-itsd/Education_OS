"""The widget endpoint GET /stats/contracts-expiring, and who may call what."""

from conftest import BASE, contract_body, days


def test_contracts_expiring_for_the_widget(desk, monkeypatch):
    soon = desk.active(title="Generator AMC", start_date=days(-300), end_date=days(15))
    past = desk.active(title="UPS AMC", start_date=days(-400), end_date=days(-3))
    far = desk.active(title="Chiller AMC", start_date=days(-10), end_date=days(200))
    renewing = desk.active(title="Lift AMC", start_date=days(-300), end_date=days(40))
    desk.ok(desk.post(f"/contracts/{renewing['id']}/renew", {"end_date": days(400)}))
    desk.draft(start_date=days(1), end_date=days(20))  # drafts never count

    body = desk.ok(desk.get("/stats/contracts-expiring", desk.viewer))
    assert (body["within_days"], body["expiring_count"], body["expired_count"]) == (60, 2, 1)
    assert [i["contract_id"] for i in body["items"]] == [past["id"], soon["id"], renewing["id"]]
    assert [i["days_left"] for i in body["items"]] == [-3, 15, 40]
    assert [i["renewal_draft_exists"] for i in body["items"]] == [False, False, True]
    first = body["items"][0]
    assert set(first) == {
        "contract_id",
        "number",
        "vendor_id",
        "title",
        "end_date",
        "days_left",
        "renewal_draft_exists",
    }
    assert far["id"] not in {i["contract_id"] for i in body["items"]}

    narrow = desk.ok(desk.get("/stats/contracts-expiring?within_days=20"))
    assert [i["contract_id"] for i in narrow["items"]] == [past["id"], soon["id"]]
    monkeypatch.setenv("AMC_VENDOR_SUPPORT_EXPIRY_WINDOW_DAYS", "365")
    assert desk.ok(desk.get("/stats/contracts-expiring"))["within_days"] == 365
    assert desk.get("/stats/contracts-expiring?within_days=0").status_code == 422
    assert desk.get("/stats/contracts-expiring?within_days=367").status_code == 422


def test_viewer_reads_but_does_not_change_anything(desk):
    contract = desk.active()
    assert desk.get(f"/contracts/{contract['id']}", desk.viewer).status_code == 200
    assert desk.get("/engagements", desk.viewer).status_code == 200
    for path, body in [
        ("/contracts", contract_body()),
        (f"/contracts/{contract['id']}/terminate", {"reason": "No", "effective_date": days(1)}),
        ("/engagements", {"contract_id": contract["id"], "kind": "breakdown_call", "description": "Broken"}),
    ]:
        refused = desk.post(path, body, desk.viewer)
        assert (refused.status_code, refused.json()["detail"]["code"]) == (403, "forbidden"), path


def test_coordinator_raises_engagements_but_does_not_manage_contracts(desk):
    contract = desk.active()
    desk.engagement(contract["id"])
    assert desk.post(f"/contracts/{contract['id']}/renew", {"end_date": days(500)}, desk.coordinator).status_code == 403
    assert desk.patch(f"/contracts/{contract['id']}", {"owner_id": desk.viewer_id}, desk.coordinator).status_code == 403


def test_no_token_or_no_permission(client, org, clock):
    assert client.get(f"{BASE}/contracts").status_code == 401
    assert client.get(f"{BASE}/contracts", headers={"Authorization": "Bearer nonsense"}).status_code == 401
    _, stranger = org.user("helpdesk-agent")
    assert client.get(f"{BASE}/stats/contracts-expiring", headers=stranger).status_code == 403


def test_profile_role_support_staff_reads_through_its_dashboard_layout(client, org, clock):
    """support-staff.yaml gives the Support Staff profile role amc-vendor-support-viewer (module_roles)."""
    _, staff = org.user("support-staff")
    assert client.get(f"{BASE}/stats/contracts-expiring", headers=staff).status_code == 200
    assert client.post(f"{BASE}/contracts", json={}, headers=staff).status_code == 403
