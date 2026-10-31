"""HTTP route tests for workflow endpoints, permissions, and pending approvals queue."""

from eos_workflow.application import service
from workflow_support import Org, sample_chain


def test_chain_routes_require_permissions(workflow_client, workflow_db):
    org = Org(workflow_db)
    payload = sample_chain("fee_waiver")

    # Unauthenticated -> 401
    res = workflow_client.post("/api/v1/workflow/chains", json=payload)
    assert res.status_code == 401

    # Student cannot create chain -> 403
    res = workflow_client.post(
        "/api/v1/workflow/chains",
        json=payload,
        headers=org.headers(org.student),
    )
    assert res.status_code == 403

    # Org Admin can create chain -> 201
    res = workflow_client.post(
        "/api/v1/workflow/chains",
        json=payload,
        headers=org.headers(org.admin),
    )
    assert res.status_code == 201
    body = res.json()
    assert body["code"] == "fee_waiver"
    assert len(body["steps"]) == 2

    # Org Admin can list chains -> 200
    res = workflow_client.get(
        "/api/v1/workflow/chains",
        headers=org.headers(org.admin),
    )
    assert res.status_code == 200
    assert len(res.json()) == 1


def test_request_submission_and_pending_queue(workflow_client, workflow_db):
    org = Org(workflow_db)
    chain_data = sample_chain("leave_q")
    service.create_chain(
        workflow_db,
        org.id,
        code=chain_data["code"],
        title=chain_data["title"],
        description=chain_data["description"],
        steps_data=chain_data["steps"],
    )
    workflow_db.commit()

    # Faculty submits leave request -> 201
    res = workflow_client.post(
        "/api/v1/workflow/requests",
        json={
            "chain_code": "leave_q",
            "entity_type": "leave",
            "entity_id": "l-301",
            "title": "Medical Leave 3 days",
            "description": "Hospital checkup",
            "client_token": "tok-301",
        },
        headers=org.headers(org.faculty),
    )
    assert res.status_code == 201
    req_id = res.json()["id"]

    # Pending approvals for Department Admin -> contains the request
    res = workflow_client.get(
        "/api/v1/workflow/requests/pending",
        headers=org.headers(org.dept_admin),
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == req_id
    assert data["items"][0]["title"] == "Medical Leave 3 days"

    # Pending approvals for Student -> 0 (student is not approver)
    res = workflow_client.get(
        "/api/v1/workflow/requests/pending",
        headers=org.headers(org.student),
    )
    assert res.status_code == 200
    assert res.json()["total"] == 0

    # Department Admin approves Step 1 -> 200
    res = workflow_client.post(
        f"/api/v1/workflow/requests/{req_id}/approve",
        json={"comments": "Medical certificate verified"},
        headers=org.headers(org.dept_admin),
    )
    assert res.status_code == 200
    assert res.json()["current_step_order"] == 2

    # Now pending for Org Admin (Director Sign-off)
    res = workflow_client.get(
        "/api/v1/workflow/requests/pending",
        headers=org.headers(org.admin),
    )
    assert res.status_code == 200
    assert res.json()["total"] == 1


def test_request_detail_and_history(workflow_client, workflow_db):
    org = Org(workflow_db)
    chain_data = sample_chain("proc_q")
    service.create_chain(
        workflow_db,
        org.id,
        code=chain_data["code"],
        title=chain_data["title"],
        description=chain_data["description"],
        steps_data=chain_data["steps"],
    )
    workflow_db.commit()

    req, _ = service.create_request(
        workflow_db,
        org.id,
        "proc_q",
        "po",
        "po-99",
        "Lab Chemicals",
        requester_id=org.faculty.id,
    )
    workflow_db.commit()

    # Reject request
    service.reject_request(
        workflow_db,
        org.id,
        req.id,
        actor_id=org.dept_admin.id,
        actor_name="HoD Chemistry",
        actor_roles=["department-admin"],
        comments="Supplier not empanelled",
    )
    workflow_db.commit()

    # Get details with history
    res = workflow_client.get(
        f"/api/v1/workflow/requests/{req.id}",
        headers=org.headers(org.dept_admin),
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "rejected"
    assert len(body["history"]) == 1
    assert body["history"][0]["action"] == "rejected"
    assert body["history"][0]["comments"] == "Supplier not empanelled"


def test_requester_cannot_approve_reject_or_delegate_over_http(workflow_client, workflow_db):
    org = Org(workflow_db)
    chain_data = sample_chain("self_http")
    service.create_chain(
        workflow_db,
        org.id,
        code=chain_data["code"],
        title=chain_data["title"],
        description=chain_data["description"],
        steps_data=chain_data["steps"],
    )
    workflow_db.commit()

    # Org admin submits a request
    res = workflow_client.post(
        "/api/v1/workflow/requests",
        json={
            "chain_code": "self_http",
            "entity_type": "capex",
            "entity_id": "cx-1",
            "title": "Admin Equipment",
        },
        headers=org.headers(org.admin),
    )
    assert res.status_code == 201
    req_id = res.json()["id"]

    # Org admin attempts to approve own request -> 403
    res = workflow_client.post(
        f"/api/v1/workflow/requests/{req_id}/approve",
        headers=org.headers(org.admin),
    )
    assert res.status_code == 403
    assert "Requesters cannot" in res.json()["detail"]

    # Org admin attempts to reject own request -> 403
    res = workflow_client.post(
        f"/api/v1/workflow/requests/{req_id}/reject",
        headers=org.headers(org.admin),
    )
    assert res.status_code == 403

    # Org admin attempts to delegate own request -> 403
    res = workflow_client.post(
        f"/api/v1/workflow/requests/{req_id}/delegate",
        json={"delegate_to_user_id": org.dept_admin.id},
        headers=org.headers(org.admin),
    )
    assert res.status_code == 403


def test_student_and_faculty_scoped_to_own_requests(workflow_client, workflow_db):
    org = Org(workflow_db)
    chain_data = sample_chain("scoped_read")
    service.create_chain(
        workflow_db,
        org.id,
        code=chain_data["code"],
        title=chain_data["title"],
        description=chain_data["description"],
        steps_data=chain_data["steps"],
    )
    workflow_db.commit()

    # Student 1 submits request
    res1 = workflow_client.post(
        "/api/v1/workflow/requests",
        json={
            "chain_code": "scoped_read",
            "entity_type": "club",
            "entity_id": "c-1",
            "title": "Robotics Club",
        },
        headers=org.headers(org.student),
    )
    assert res1.status_code == 201
    req1_id = res1.json()["id"]

    # Faculty submits request
    res2 = workflow_client.post(
        "/api/v1/workflow/requests",
        json={
            "chain_code": "scoped_read",
            "entity_type": "grant",
            "entity_id": "g-1",
            "title": "Research Grant",
        },
        headers=org.headers(org.faculty),
    )
    assert res2.status_code == 201
    req2_id = res2.json()["id"]

    # Student listing requests only sees student's own request
    res = workflow_client.get(
        "/api/v1/workflow/requests",
        headers=org.headers(org.student),
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == req1_id

    # Student trying to get faculty request -> 404
    res = workflow_client.get(
        f"/api/v1/workflow/requests/{req2_id}",
        headers=org.headers(org.student),
    )
    assert res.status_code == 404

    # Faculty trying to get student request -> 404
    res = workflow_client.get(
        f"/api/v1/workflow/requests/{req1_id}",
        headers=org.headers(org.faculty),
    )
    assert res.status_code == 404

    # Admin listing requests sees both
    res = workflow_client.get(
        "/api/v1/workflow/requests",
        headers=org.headers(org.admin),
    )
    assert res.status_code == 200
    assert res.json()["total"] == 2

    # Admin can get either request -> 200
    assert (
        workflow_client.get(f"/api/v1/workflow/requests/{req1_id}", headers=org.headers(org.admin)).status_code == 200
    )
    assert (
        workflow_client.get(f"/api/v1/workflow/requests/{req2_id}", headers=org.headers(org.admin)).status_code == 200
    )
