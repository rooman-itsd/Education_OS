"""API route tests for reporting: permissions, execution, exports, and widgets."""

from __future__ import annotations

from eos_reporting.application import service


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
    download_url = r_exp.json()["download_url"]
    assert "download_url" in r_exp.json()

    # Verify that the download URL returns valid file content
    r_dl = client.get(download_url, headers=org.admin_headers)
    assert r_dl.status_code == 200
    assert "text/csv" in r_dl.headers.get("content-type", "")
    assert "attachment" in r_dl.headers.get("content-disposition", "")
    assert len(r_dl.content) > 0

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


def test_download_requires_execute_permission(client, org):
    defs = client.get("/api/v1/reporting/definitions", headers=org.admin_headers).json()
    exec_id = client.post(f"/api/v1/reporting/definitions/{defs[0]['id']}/run", headers=org.admin_headers).json()["id"]
    url = f"/api/v1/reporting/executions/{exec_id}/download?format=csv"

    # Faculty holds reporting:report:read only: blocked from both export and direct download
    assert client.get(f"/api/v1/reporting/executions/{exec_id}/export", headers=org.faculty_headers).status_code == 403
    assert client.get(url, headers=org.faculty_headers).status_code == 403

    # Department admin holds reporting:report:execute
    r = client.get(url, headers=org.dept_admin_headers)
    assert r.status_code == 200
    assert "attachment" in r.headers.get("content-disposition", "")


def test_new_organisation_lists_standard_definitions(client, unseeded_org):
    r = client.get("/api/v1/reporting/definitions", headers=unseeded_org.faculty_headers)
    assert r.status_code == 200
    defs = r.json()
    system_codes = sorted(d["code"] for d in defs if d["is_system"])
    assert system_codes == sorted(d["code"] for d in service.STANDARD_DEFINITIONS)

    # Listing again does not duplicate them
    again = client.get("/api/v1/reporting/definitions", headers=unseeded_org.faculty_headers).json()
    assert len(again) == len(defs)

    # A standard report can be run by id (not only by code)
    attendance = next(d for d in defs if d["code"] == "department-attendance")
    r_run = client.post(
        f"/api/v1/reporting/definitions/{attendance['id']}/run", headers=unseeded_org.dept_admin_headers
    )
    assert r_run.status_code == 201
    assert r_run.json()["report_definition_id"] == attendance["id"]


def test_concurrent_duplicate_create_returns_409(client, org, monkeypatch):
    body = {"code": "race-report", "name": "Race", "category": "academic"}
    assert client.post("/api/v1/reporting/definitions", json=body, headers=org.admin_headers).status_code == 201

    # Simulate the second request passing the existence check before the first commits
    monkeypatch.setattr(service, "get_definition", lambda *a, **k: None)
    r = client.post("/api/v1/reporting/definitions", json=body, headers=org.admin_headers)
    assert r.status_code == 409


def test_system_definition_rejects_blank_field_changes(client, org):
    defs = client.get("/api/v1/reporting/definitions", headers=org.admin_headers).json()
    system_id = next(d["id"] for d in defs if d["is_system"])
    url = f"/api/v1/reporting/definitions/{system_id}"
    assert client.put(url, json={"name": ""}, headers=org.admin_headers).status_code == 403
    assert client.put(url, json={"parameters_schema": {}}, headers=org.admin_headers).status_code == 403
    # Toggling active state stays allowed
    assert client.put(url, json={"is_active": False}, headers=org.admin_headers).status_code == 200
