"""Security regressions for who may read and act on workflow requests (audit of #317, follow-up).

- client_token is per requester: replaying another user's token never returns their request.
- a non-admin reads their own requests, those delegated to them, those they acted on, and (approvers only)
  those that reached a step their role approves. Org and super admins read everything.
- an action names the step it decides; a step another approver already decided is refused, never applied to
  the next step.
"""

from __future__ import annotations

from workflow_support import PREFIX, Org, sample_chain


def _chain(client, org, code, steps):
    res = client.post(
        f"{PREFIX}/chains",
        json={"code": code, "title": code, "steps": steps},
        headers=org.headers(org.admin),
    )
    assert res.status_code == 201, res.text
    return res.json()


def _submit(client, org, user, chain_code, **extra):
    body = {"chain_code": chain_code, "entity_type": "leave", "entity_id": "e-1", "title": "Request", **extra}
    return client.post(f"{PREFIX}/requests", json=body, headers=org.headers(user))


def _ids(res):
    assert res.status_code == 200, res.text
    return {r["id"] for r in res.json()["items"]}


def test_client_token_replay_by_another_user_creates_their_own_request(workflow_client, workflow_db):
    org = Org(workflow_db)
    _chain(workflow_client, org, "leave", sample_chain()["steps"])

    first = _submit(workflow_client, org, org.faculty, "leave", client_token="tok", context={"reason": "medical"})
    assert first.status_code == 201

    # Same token, different user: a new request of their own, not the faculty member's (or its context)
    other = _submit(workflow_client, org, org.student, "leave", client_token="tok")
    assert other.status_code == 201
    assert other.json()["id"] != first.json()["id"]
    assert other.json()["requester_id"] == org.student.id
    assert other.json()["context"] == {}

    # The original requester's replay is still idempotent
    replay = _submit(workflow_client, org, org.faculty, "leave", client_token="tok")
    assert replay.status_code == 200
    assert replay.json()["id"] == first.json()["id"]


def test_department_admin_reads_only_requests_routed_to_their_role(workflow_client, workflow_db):
    org = Org(workflow_db)
    _chain(workflow_client, org, "leave", sample_chain()["steps"])  # step 1 department-admin, step 2 org-admin
    _chain(
        workflow_client,
        org,
        "grievance",
        [{"step_order": 1, "name": "Director", "approver_role": "org-admin", "is_final": True}],
    )
    leave = _submit(workflow_client, org, org.student, "leave").json()
    grievance = _submit(workflow_client, org, org.student, "grievance", context={"about": "harassment"}).json()

    dept = org.headers(org.dept_admin)
    assert workflow_client.get(f"{PREFIX}/requests/{leave['id']}", headers=dept).status_code == 200
    assert workflow_client.get(f"{PREFIX}/requests/{grievance['id']}", headers=dept).status_code == 404
    listed = workflow_client.get(f"{PREFIX}/requests", headers=dept)
    assert _ids(listed) == {leave["id"]}
    assert listed.json()["total"] == 1
    # Filtering by requester cannot widen what they see
    assert _ids(workflow_client.get(f"{PREFIX}/requests?requester_id={org.student.id}", headers=dept)) == {leave["id"]}

    # Org admin reads both; the student reads both of their own; faculty read none of them
    assert _ids(workflow_client.get(f"{PREFIX}/requests", headers=org.headers(org.admin))) == {
        leave["id"],
        grievance["id"],
    }
    assert _ids(workflow_client.get(f"{PREFIX}/requests", headers=org.headers(org.student))) == {
        leave["id"],
        grievance["id"],
    }
    assert _ids(workflow_client.get(f"{PREFIX}/requests", headers=org.headers(org.faculty))) == set()
    assert workflow_client.get(f"{PREFIX}/requests/{leave['id']}", headers=org.headers(org.faculty)).status_code == 404


def test_step_role_held_by_a_non_approver_grants_no_read(workflow_client, workflow_db):
    org = Org(workflow_db)
    # A chain naming 'faculty' as the approver role: faculty hold no workflow:approval:action, so they can
    # neither act on nor read other people's requests through it.
    _chain(
        workflow_client,
        org,
        "odd",
        [{"step_order": 1, "name": "Faculty", "approver_role": "faculty", "is_final": True}],
    )
    req = _submit(workflow_client, org, org.student, "odd").json()
    fac = org.headers(org.faculty)
    assert workflow_client.get(f"{PREFIX}/requests/{req['id']}", headers=fac).status_code == 404
    assert _ids(workflow_client.get(f"{PREFIX}/requests", headers=fac)) == set()


def test_delegate_reads_and_acts_on_the_delegated_request(workflow_client, workflow_db):
    org = Org(workflow_db)
    _chain(
        workflow_client,
        org,
        "grievance",
        [{"step_order": 1, "name": "Director", "approver_role": "org-admin", "is_final": True}],
    )
    req = _submit(workflow_client, org, org.student, "grievance").json()
    dept = org.headers(org.dept_admin)
    assert workflow_client.get(f"{PREFIX}/requests/{req['id']}", headers=dept).status_code == 404

    res = workflow_client.post(
        f"{PREFIX}/requests/{req['id']}/delegate",
        json={"delegate_to_user_id": org.dept_admin.id},
        headers=org.headers(org.admin),
    )
    assert res.status_code == 200, res.text

    assert workflow_client.get(f"{PREFIX}/requests/{req['id']}", headers=dept).status_code == 200
    assert req["id"] in _ids(workflow_client.get(f"{PREFIX}/requests/pending", headers=dept))
    res = workflow_client.post(f"{PREFIX}/requests/{req['id']}/approve", json={}, headers=dept)
    assert res.status_code == 200 and res.json()["status"] == "approved"
    # Having acted on it, they can still read it after the delegation is cleared
    assert workflow_client.get(f"{PREFIX}/requests/{req['id']}", headers=dept).status_code == 200


def test_delegating_to_someone_who_cannot_act_is_refused(workflow_client, workflow_db):
    org = Org(workflow_db)
    _chain(workflow_client, org, "leave", sample_chain()["steps"])
    req = _submit(workflow_client, org, org.student, "leave").json()
    res = workflow_client.post(
        f"{PREFIX}/requests/{req['id']}/delegate",
        json={"delegate_to_user_id": org.faculty.id},
        headers=org.headers(org.dept_admin),
    )
    assert res.status_code == 422


def test_action_on_an_already_decided_step_is_refused(workflow_client, workflow_db):
    org = Org(workflow_db)
    _chain(workflow_client, org, "leave", sample_chain()["steps"])
    req = _submit(workflow_client, org, org.student, "leave").json()

    first = workflow_client.post(
        f"{PREFIX}/requests/{req['id']}/approve", json={"step_order": 1}, headers=org.headers(org.dept_admin)
    )
    assert first.status_code == 200 and first.json()["current_step_order"] == 2

    # The org admin was also looking at step 1: their approval must not silently sign off step 2
    late = workflow_client.post(
        f"{PREFIX}/requests/{req['id']}/approve", json={"step_order": 1}, headers=org.headers(org.admin)
    )
    assert late.status_code == 409
    late_reject = workflow_client.post(
        f"{PREFIX}/requests/{req['id']}/reject", json={"step_order": 1}, headers=org.headers(org.admin)
    )
    assert late_reject.status_code == 409

    detail = workflow_client.get(f"{PREFIX}/requests/{req['id']}", headers=org.headers(org.admin)).json()
    assert detail["status"] == "pending" and detail["current_step_order"] == 2
    assert [a["action"] for a in detail["history"]] == ["approved"]


def test_duplicate_chain_code_after_trimming_returns_409(workflow_client, workflow_db):
    org = Org(workflow_db)
    steps = sample_chain()["steps"]
    _chain(workflow_client, org, "leave", steps)
    res = workflow_client.post(
        f"{PREFIX}/chains",
        json={"code": " leave ", "title": "Leave again", "steps": steps},
        headers=org.headers(org.admin),
    )
    assert res.status_code == 409


def test_pending_queue_needs_the_approval_permission_like_every_other_read(workflow_client, workflow_db):
    """`GET /requests/pending` matched a non-admin on the step's role name alone. A role that may read requests but
    holds no `workflow:approval:action` (faculty, student) therefore listed the current-step requests of any chain
    that names it as approver, while `GET /requests/{id}` answered 404 for the same request."""
    org = Org(workflow_db)
    _chain(
        workflow_client,
        org,
        "peer-review",
        [{"step_order": 1, "name": "Peer", "approver_role": "faculty", "is_final": True}],
    )
    sent = _submit(workflow_client, org, org.student, "peer-review", context={"about": "private"}).json()

    faculty = org.headers(org.faculty)
    assert workflow_client.get(f"{PREFIX}/requests/{sent['id']}", headers=faculty).status_code == 404
    pending = workflow_client.get(f"{PREFIX}/requests/pending", headers=faculty)
    assert pending.status_code == 200, pending.text
    assert pending.json() == {"items": [], "total": 0}

    # An approver who does hold the permission still sees what is routed to their role.
    chain_for_dept = _chain(
        workflow_client,
        org,
        "leave2",
        [{"step_order": 1, "name": "HoD", "approver_role": "department-admin", "is_final": True}],
    )
    assert chain_for_dept
    leave = _submit(workflow_client, org, org.student, "leave2").json()
    assert _ids(workflow_client.get(f"{PREFIX}/requests/pending", headers=org.headers(org.dept_admin))) == {leave["id"]}


def test_a_modules_entity_type_cannot_be_created_over_http(workflow_client, workflow_db):
    """Security review N6 (#673): `<module>.<type>` entity types are reserved for eos_core.workflow.submit, so the
    approval of a request a student made up can never be taken by a module for its own record. Nothing is written."""
    org = Org(workflow_db)
    _chain(workflow_client, org, "leave", sample_chain()["steps"])
    for user in (org.student, org.faculty, org.admin):
        res = _submit(workflow_client, org, user, "leave", entity_type="examinations.result_set")
        assert res.status_code == 403, res.text
        assert res.json()["code"] == "reserved_entity_type"
    listed = workflow_client.get(f"{PREFIX}/requests", headers=org.headers(org.admin))
    assert listed.status_code == 200 and listed.json()["total"] == 0
    assert _submit(workflow_client, org, org.student, "leave").status_code == 201  # a plain type is still filed
