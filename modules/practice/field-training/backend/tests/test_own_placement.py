"""Nobody acts on their own placement, whatever else they hold: a user with the coordinator role and the trainee role
cannot approve their own application (found in the review of #504)."""

from conftest import TODAY  # noqa: F401  (the fixtures' day; imported so a rename shows here)


def both(prog):
    """A user who is a coordinator and a trainee at once."""
    return prog.org.user("field-training-coordinator", "field-training-trainee")


def refused(response):
    assert response.status_code == 403, response.text
    assert response.json()["detail"]["code"] == "own_placement"


def test_a_coordinator_cannot_approve_or_reject_their_own_application(prog):
    me_id, me = both(prog)
    p = prog.ok(prog.post(f"/openings/{prog.opening['id']}/apply", None, me), 201)
    refused(prog.post(f"/placements/{p['id']}/decision", {"decision": "approved"}, me))
    refused(prog.post(f"/placements/{p['id']}/decision", {"decision": "rejected", "reason": "Not for me"}, me))
    assert prog.get(f"/placements/{p['id']}", me).json()["status"] == "requested"  # nothing changed
    # Another coordinator decides it.
    approved = prog.ok(prog.post(f"/placements/{p['id']}/decision", {"decision": "approved"}, prog.coordinator))
    assert approved["status"] == "assigned" and approved["trainee_id"] == me_id


def test_a_coordinator_cannot_assign_start_change_or_complete_their_own_placement(prog):
    me_id, me = both(prog)
    refused(prog.post("/placements", {"opening_id": prog.opening["id"], "trainee_id": me_id}, me))
    # Someone else assigns them; from then on they hold a placement and the coordinator role.
    p = prog.ok(
        prog.post("/placements", {"opening_id": prog.opening["id"], "trainee_id": me_id}, prog.coordinator), 201
    )
    refused(prog.post(f"/placements/{p['id']}/start", None, me))
    refused(prog.patch(f"/placements/{p['id']}", {"supervisor_id": prog.supervisor_id}, me))
    started = prog.ok(prog.post(f"/placements/{p['id']}/start", None, prog.coordinator))
    refused(prog.post(f"/placements/{p['id']}/complete", {"override": True, "reason": "I am done with it"}, me))
    assert prog.get(f"/placements/{started['id']}", me).json()["status"] == "active"


def test_a_coordinator_trainee_cannot_withdraw_their_own_active_placement(prog):
    _, me = both(prog)
    q = prog.ok(prog.post(f"/openings/{prog.opening['id']}/apply", None, me), 201)
    prog.ok(prog.post(f"/placements/{q['id']}/decision", {"decision": "approved"}, prog.coordinator))
    # Before it starts they may withdraw it, as any trainee may.
    withdrawn = prog.ok(prog.post(f"/placements/{q['id']}/withdraw", {"reason": "Changed my mind"}, me))
    assert withdrawn["status"] == "withdrawn"
    # Once active, only another coordinator withdraws it, as for a trainee-only user.
    other_id, other = both(prog)
    p = prog.ok(
        prog.post("/placements", {"opening_id": prog.opening["id"], "trainee_id": other_id}, prog.coordinator), 201
    )
    prog.ok(prog.post(f"/placements/{p['id']}/start", None, prog.coordinator))
    r = prog.post(f"/placements/{p['id']}/withdraw", {"reason": "Leaving the programme"}, other)
    assert r.status_code == 403 and r.json()["detail"]["code"] == "placement_active"
    ok = prog.ok(prog.post(f"/placements/{p['id']}/withdraw", {"reason": "Leaving the programme"}, prog.coordinator))
    assert ok["status"] == "withdrawn"


def test_a_coordinator_still_manages_everyone_elses_placements(prog):
    _, me = both(prog)
    trainee_id, _, p = prog.assigned()
    started = prog.ok(prog.post(f"/placements/{p['id']}/start", None, me))  # a coordinator who is nobody's trainee here
    assert started["status"] == "active" and started["trainee_id"] == trainee_id


# ---- ids are one id whatever their case (found in the review of #504)


def test_the_own_placement_guard_ignores_the_case_of_the_id(prog):
    me_id, me = both(prog)
    # Assign yourself with your own id in capitals: still your own placement.
    refused(prog.post("/placements", {"opening_id": prog.opening["id"], "trainee_id": me_id.upper()}, me))
    # Someone else assigns you, with the id in capitals; it is stored in lowercase and the guard still applies.
    p = prog.ok(
        prog.post(
            "/placements", {"opening_id": prog.opening["id"].upper(), "trainee_id": me_id.upper()}, prog.coordinator
        ),
        201,
    )
    assert p["trainee_id"] == me_id and p["opening_id"] == prog.opening["id"]
    refused(prog.post(f"/placements/{p['id']}/start", None, me))
    refused(prog.post(f"/placements/{p['id'].upper()}/start", None, me))  # the path id in capitals too
    assert prog.get(f"/placements/{p['id']}", me).json()["status"] == "assigned"  # nothing changed


def test_a_token_with_the_user_id_in_capitals_is_the_same_user(prog):
    from eos_core.security import create_token

    me_id, _ = both(prog)
    token = create_token(
        user_id=me_id.upper(),
        organisation_id=prog.org.id.upper(),
        roles=["field-training-coordinator", "field-training-trainee"],
    )
    me = {"Authorization": f"Bearer {token}"}
    p = prog.ok(prog.post(f"/openings/{prog.opening['id']}/apply", None, me), 201)
    assert p["trainee_id"] == me_id  # stored in lowercase, in the same organisation
    refused(prog.post(f"/placements/{p['id']}/decision", {"decision": "approved"}, me))


def test_ids_are_stored_in_lowercase_and_supervisors_are_unique_whatever_the_case(prog):
    c = prog
    sup = c.supervisor_id
    r = c.ok(
        c.patch(
            f"/sites/{c.site['id'].upper()}",
            {"name": c.site["name"], "supervisor_ids": [sup, sup.upper()]},
            c.coordinator,
        )
    )
    assert r["supervisor_ids"] == [sup] and r["id"] == c.site["id"]
    assert c.ok(c.get(f"/sites/{c.site['id'].upper()}", c.coordinator))["id"] == c.site["id"]
    assert c.ok(c.get(f"/openings?site_id={c.site['id'].upper()}", c.coordinator))["items"]
