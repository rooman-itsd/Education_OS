"""API route tests for documents: permissions, validation, and responses."""

from eos_documents.application import service


def test_routes_require_authentication(client):
    # No auth header -> 401
    assert client.post("/api/v1/documents/upload-intent", json={}).status_code == 401
    assert client.get("/api/v1/documents/doc-1").status_code == 401
    assert client.get("/api/v1/documents/").status_code == 401
    assert client.delete("/api/v1/documents/doc-1").status_code == 401


def test_upload_intent_and_permissions(client, org):
    payload = {
        "filename": "thesis.pdf",
        "mime_type": "application/pdf",
        "size_bytes": 10240,
        "title": "Master Thesis Draft",
        "client_token": "client-tok-1",
    }

    # Faculty has write permission -> 201
    r = client.post("/api/v1/documents/upload-intent", json=payload, headers=org.faculty_headers)
    assert r.status_code == 201, r.text
    data = r.json()
    assert "upload_url" in data
    assert data["document"]["filename"] == "thesis.pdf"
    assert data["document"]["client_token"] == "client-tok-1"

    # Replay -> 200
    r_replay = client.post("/api/v1/documents/upload-intent", json=payload, headers=org.faculty_headers)
    assert r_replay.status_code == 200
    assert r_replay.json()["document"]["id"] == data["document"]["id"]


def test_confirm_and_download_flow(client, org, db):
    # 1. Request upload intent
    r = client.post(
        "/api/v1/documents/upload-intent",
        json={"filename": "certificate.pdf", "mime_type": "application/pdf", "size_bytes": 5000},
        headers=org.student_headers,
    )
    assert r.status_code == 201
    doc_id = r.json()["document"]["id"]

    # 2. Confirm before storage put -> 400
    r_bad_confirm = client.post(f"/api/v1/documents/{doc_id}/confirm", headers=org.student_headers)
    assert r_bad_confirm.status_code == 400

    # 3. Simulate client PUT into storage
    doc = service.get_document(db, org.id, doc_id)
    store = service.get_storage()
    store.put_object(doc.bucket, doc.storage_path, b"dummy binary data", doc.mime_type)

    # 4. Confirm upload -> 200
    r_confirm = client.post(f"/api/v1/documents/{doc_id}/confirm", headers=org.student_headers)
    assert r_confirm.status_code == 200
    assert r_confirm.json()["status"] == "available"

    # 5. Get document metadata -> 200
    r_get = client.get(f"/api/v1/documents/{doc_id}", headers=org.student_headers)
    assert r_get.status_code == 200
    assert r_get.json()["id"] == doc_id

    # 6. Get download URL -> 200
    r_dl = client.get(f"/api/v1/documents/{doc_id}/download-url", headers=org.student_headers)
    assert r_dl.status_code == 200
    assert "download_url" in r_dl.json()


def test_delete_permission_enforcement(client, org, db):
    # Direct upload document
    doc = service.direct_upload(
        db,
        org.id,
        org.faculty_id,
        "grade_sheet.pdf",
        "application/pdf",
        b"grades",
    )
    db.commit()

    # Student lacks documents:document:delete -> 403
    r_forbidden = client.delete(f"/api/v1/documents/{doc.id}", headers=org.student_headers)
    assert r_forbidden.status_code == 403

    # Org-admin has documents:document:delete -> 200
    r_delete = client.delete(f"/api/v1/documents/{doc.id}", headers=org.admin_headers)
    assert r_delete.status_code == 200
    assert r_delete.json()["deleted"] is True


def test_cross_tenant_isolation_via_api(client, org, other_org, db):
    doc = service.direct_upload(
        db,
        org.id,
        org.faculty_id,
        "org1_secret.pdf",
        "application/pdf",
        b"top secret",
    )
    db.commit()

    # other_org attempts to read doc -> 404
    r = client.get(f"/api/v1/documents/{doc.id}", headers=other_org.admin_headers)
    assert r.status_code == 404

    # other_org attempts to download doc -> 404
    r_dl = client.get(f"/api/v1/documents/{doc.id}/download-url", headers=other_org.admin_headers)
    assert r_dl.status_code == 404

    # other_org attempts to delete doc -> 404
    r_del = client.delete(f"/api/v1/documents/{doc.id}", headers=other_org.admin_headers)
    assert r_del.status_code == 404
