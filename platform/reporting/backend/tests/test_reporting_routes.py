"""API route tests for reporting: permissions, execution, exports, and widgets."""

from __future__ import annotations


def test_routes_require_authentication(client):
    assert client.get("/api/v1/reporting/definitions").status_code == 401
    assert client.post("/api/v1/reporting/definitions", json={}).status_code == 401
    assert client.post("/api/v1/reporting/definitions/def-1/run").status_code == 401
    assert client.get("/api/v1/reporting/widgets/department-reports").status_code == 401
    assert client.get("/api/v1/reporting/widgets/attendance-and-results").status_code == 401


def test_definitions_and_permission_enforcement(client, org):
    # Faculty can read definitions
    r = client.get("/api/v1/reporting/definitions", headers=org.faculty_headers)
    assert r.status_code == 200
    defs = r.json()
    assert len(defs) >= 4

    # Faculty cannot create custom definition (needs reporting:report:manage)
    r = client.post(
        "/api/v1/reporting/definitions",
        json={"code": "custom-1", "name": "Custom 1", "category": "academic"},
        headers=org.faculty_headers,
    )
    assert r.status_code == 403

    # Org Admin can create custom definition
    r = client.post(
        "/api/v1/reporting/definitions",
        json={"code": "faculty-evaluations", "name": "Faculty Student Evaluations", "category": "academic"},
        headers=org.admin_headers,
    )
    assert r.status_code == 201
    assert r.json()["code"] == "faculty-evaluations"


def test_run_report_via_api_and_idempotency(client, org):
    defs = client.get("/api/v1/reporting/definitions", headers=org.admin_headers).json()
    def_id = defs[0]["id"]

    # Student cannot execute reports (lacks reporting:report:execute)
    r = client.post(f"/api/v1/reporting/definitions/{def_id}/run", headers=org.student_headers)
    assert r.status_code == 403

    # Department admin can execute report
    token = "api-token-456"
    r = client.post(
        f"/api/v1/reporting/definitions/{def_id}/run",
        json={"parameters": {"department_id": "dept-cs"}, "client_token": token},
        headers=org.dept_admin_headers,
    )
    assert r.status_code == 201
    data = r.json()
    exec_id = data["id"]
    assert data["status"] == "completed"

    # Replayed token returns 200 with same execution
    r_replay = client.post(
        f"/api/v1/reporting/definitions/{def_id}/run",
        json={"parameters": {"department_id": "dept-cs"}, "client_token": token},
        headers=org.dept_admin_headers,
    )
    assert r_replay.status_code == 200
    assert r_replay.json()["id"] == exec_id


def test_export_and_widgets_via_api(client, org, memory_storage):
    defs = client.get("/api/v1/reporting/definitions", headers=org.admin_headers).json()
    run_res = client.post(f"/api/v1/reporting/definitions/{defs[0]['id']}/run", headers=org.admin_headers).json()
    exec_id = run_res["id"]

    # Export as CSV
    r_exp = client.get(f"/api/v1/reporting/executions/{exec_id}/export?format=csv", headers=org.admin_headers)
    assert r_exp.status_code == 200
    assert r_exp.json()["format"] == "csv"
    assert "download_url" in r_exp.json()

    # Department widget route
    r_dept = client.get("/api/v1/reporting/widgets/department-reports", headers=org.dept_admin_headers)
    assert r_dept.status_code == 200
    assert "attendance_rate" in r_dept.json()

    # Management widget route
    r_mgmt = client.get("/api/v1/reporting/widgets/attendance-and-results", headers=org.management_headers)
    assert r_mgmt.status_code == 200
    assert "institution_average_attendance" in r_mgmt.json()


def test_cross_tenant_isolation_via_api(client, org, other_org):
    # Org 1 creates custom report
    r = client.post(
        "/api/v1/reporting/definitions",
        json={"code": "org1-confidential", "name": "Org 1 Confidential", "category": "financial"},
        headers=org.admin_headers,
    )
    assert r.status_code == 201
    org1_def_id = r.json()["id"]

    # Org 2 cannot read Org 1's custom definition by ID
    r_other = client.get(f"/api/v1/reporting/definitions/{org1_def_id}", headers=other_org.admin_headers)
    assert r_other.status_code == 404

    # Org 1 runs a report
    run_res = client.post(f"/api/v1/reporting/definitions/{org1_def_id}/run", headers=org.admin_headers).json()
    exec_id = run_res["id"]

    # Org 2 cannot read Org 1's execution
    r_exec_other = client.get(f"/api/v1/reporting/executions/{exec_id}", headers=other_org.admin_headers)
    assert r_exec_other.status_code == 404
