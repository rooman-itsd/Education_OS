"""Decisions by the competent authority, and who can see which file: holders, read-all, confidential files."""

from eo_support import BASE, decide, forward, note, open_file, outbox


def test_a_decision_needs_the_permission_and_the_file(client, org):
    f = open_file(client, org)
    r = decide(client, org, f, "hr")
    assert r.status_code == 403  # hr-staff cannot decide
    forward(client, org, f, "hr", "dept", action_required="for approval")
    r = decide(client, org, f, "manager")
    assert r.status_code == 409 and r.json()["detail"]["code"] == "not_holder"  # management reads it, not holds it
    forward(client, org, f, "dept", "finance")
    assert decide(client, org, f, "dept").json()["detail"]["code"] == "not_holder"


def test_the_holder_decides_and_the_decision_becomes_a_noting(client, org):
    f = open_file(client, org, first_note="Proposal to revise leave rules.")
    forward(client, org, f, "hr", "dept", action_required="for approval")
    r = decide(client, org, f, "dept", "returned", remark="Add the cost estimate.")
    assert r.status_code == 200, r.text
    got = r.json()
    assert got["last_decision"] == "returned" and got["holder"]["user_id"] == org.ids["dept"]
    last = got["notes"][-1]
    assert (last["sequence"], last["kind"], last["text"]) == (
        2,
        "decision",
        "Returned for revision. Add the cost estimate.",
    )
    assert outbox("e-office.file.decided", org.id) == [
        {
            "organisation_id": org.id,
            "file_id": f["id"],
            "number": f["number"],
            "decision": "returned",
            "decided_by": org.ids["dept"],
        }
    ]
    assert "cost estimate" not in str(outbox("e-office.file.decided", org.id))
    # a later decision replaces the last one
    assert decide(client, org, f, "dept", "approved").json()["last_decision"] == "approved"
    kinds = [m["kind"] for m in client.get(f"{BASE}/files/{f['id']}/movements", headers=org.dept).json()]
    assert kinds == ["created", "forwarded", "decided", "decided"]


def test_decide_and_forward_in_one_step(client, org):
    f = open_file(client, org)
    forward(client, org, f, "hr", "dept")
    r = decide(client, org, f, "dept", "rejected", remark="Not now.", forward_to_user_id=org.ids["hr"])
    assert r.status_code == 200
    got = r.json()
    assert got["holder"]["user_id"] == org.ids["hr"] and got["last_decision"] == "rejected"
    assert got["action_required"] == "decision rejected"
    assert outbox("e-office.file.forwarded", org.id)[-1]["to_user_id"] == org.ids["hr"]
    r = decide(client, org, f, "dept", forward_to_user_id=org.ids["dept"])
    assert r.status_code == 409  # the department admin no longer holds it


def test_decision_validation(client, org):
    f = open_file(client, org)
    forward(client, org, f, "hr", "dept")
    for body in (
        {"decision": "maybe", "remark": "x"},
        {"decision": "approved"},
        {"decision": "approved", "remark": ""},
    ):
        assert client.post(f"{BASE}/files/{f['id']}/decision", json=body, headers=org.dept).status_code == 422
    r = decide(client, org, f, "dept", remark="   ")
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_remark"
    r = decide(client, org, f, "dept", forward_to_user_id=org.ids["dept"])
    assert r.status_code == 422 and r.json()["detail"]["code"] == "same_holder"
    assert client.get(f"{BASE}/files/{f['id']}", headers=org.dept).json()["last_decision"] is None  # nothing kept


def test_everyone_who_held_a_file_keeps_seeing_it(client, org):
    f = open_file(client, org)
    forward(client, org, f, "hr", "finance")
    forward(client, org, f, "finance", "dept")
    for who in ("hr", "finance", "dept"):
        assert client.get(f"{BASE}/files/{f['id']}", headers=org.headers[who]).status_code == 200, who
        assert f["id"] in [x["id"] for x in client.get(f"{BASE}/files", headers=org.headers[who]).json()["items"]]
    assert client.get(f"{BASE}/files/{f['id']}", headers=org.faculty).status_code == 404
    assert f["id"] not in [x["id"] for x in client.get(f"{BASE}/files", headers=org.faculty).json()["items"]]


def test_read_all_sees_every_non_confidential_file_but_not_confidential_ones(client, org):
    plain = open_file(client, org, subject="Canteen tender")
    secret = open_file(client, org, subject="Disciplinary case", confidential=True)
    listed = [x["id"] for x in client.get(f"{BASE}/files", headers=org.manager).json()["items"]]
    assert plain["id"] in listed and secret["id"] not in listed
    assert client.get(f"{BASE}/files/{plain['id']}", headers=org.manager).status_code == 200
    assert client.get(f"{BASE}/files/{secret['id']}", headers=org.manager).status_code == 404
    assert client.get(f"{BASE}/files?q=disciplinary", headers=org.manager).json()["items"] == []
    # read-all is not holding: management can read the plain file but cannot note on it
    assert note(client, org, plain, "manager").json()["detail"]["code"] == "not_holder"
    # once a holder, always visible, read-all or not
    forward(client, org, secret, "hr", "manager")
    forward(client, org, secret, "manager", "dept")
    assert client.get(f"{BASE}/files/{secret['id']}", headers=org.manager).status_code == 200
    assert client.get(f"{BASE}/files/{secret['id']}/movements", headers=org.manager).status_code == 200


def test_a_confidential_file_publishes_no_subject(client, org):
    secret = open_file(client, org, subject="Disciplinary case", confidential=True)
    forward(client, org, secret, "hr", "dept")
    assert outbox("e-office.file.forwarded", org.id)[-1]["subject"] == ""
    assert outbox("e-office.file.created", org.id)[-1]["confidential"] is True
    assert "Disciplinary" not in str(
        [outbox(f"e-office.file.{x}", org.id) for x in ("created", "forwarded", "decided", "closed")]
    )
