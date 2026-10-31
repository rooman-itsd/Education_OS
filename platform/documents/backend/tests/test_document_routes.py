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
    data = b"dummy binary data"
    r = client.post(
        "/api/v1/documents/upload-intent",
        json={"filename": "certificate.pdf", "mime_type": "application/pdf", "size_bytes": len(data)},
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
    store.put_object(doc.bucket, doc.storage_path, data, doc.mime_type)

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


def test_peer_document_access_isolation_and_elevated_read_any(client, org, db):
    # Student 1 uploads doc1
    doc1 = service.direct_upload(
        db,
        org.id,
        org.student_id,
        "student1_transcript.pdf",
        "application/pdf",
        b"transcript content",
    )
    # Student 2 uploads doc2
    doc2 = service.direct_upload(
        db,
        org.id,
        org.student2_id,
        "student2_medical.pdf",
        "application/pdf",
        b"medical content",
    )
    db.commit()

    # Student 1 lists documents -> only sees doc1
    r_s1_list = client.get("/api/v1/documents/", headers=org.student_headers)
    assert r_s1_list.status_code == 200
    items = r_s1_list.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == doc1.id

    # Student 1 attempts to read doc2 -> 404
    assert client.get(f"/api/v1/documents/{doc2.id}", headers=org.student_headers).status_code == 404

    # Student 1 attempts to get download URL for doc2 -> 404
    assert client.get(f"/api/v1/documents/{doc2.id}/download-url", headers=org.student_headers).status_code == 404

    # Org Admin (holds documents:document:read-any) lists documents -> sees both
    r_admin_list = client.get("/api/v1/documents/", headers=org.admin_headers)
    assert r_admin_list.status_code == 200
    assert r_admin_list.json()["total"] == 2

    # Org Admin can read and download both
    assert client.get(f"/api/v1/documents/{doc1.id}", headers=org.admin_headers).status_code == 200
    assert client.get(f"/api/v1/documents/{doc2.id}", headers=org.admin_headers).status_code == 200
    assert client.get(f"/api/v1/documents/{doc1.id}/download-url", headers=org.admin_headers).status_code == 200
    assert client.get(f"/api/v1/documents/{doc2.id}/download-url", headers=org.admin_headers).status_code == 200


def test_confirm_upload_security_and_idempotency(client, org, db):
    store = service.get_storage()

    # 1. Non-uploader cannot confirm upload
    r_intent = client.post(
        "/api/v1/documents/upload-intent",
        json={"filename": "thesis.pdf", "mime_type": "application/pdf", "size_bytes": 100},
        headers=org.student_headers,
    )
    assert r_intent.status_code == 201
    doc_id = r_intent.json()["document"]["id"]

    # Student 2 tries to confirm -> 403
    r_hack_confirm = client.post(f"/api/v1/documents/{doc_id}/confirm", headers=org.student2_headers)
    assert r_hack_confirm.status_code == 403

    # 2. Size mismatch -> deleted from storage and 400
    doc = service.get_document(db, org.id, doc_id)
    store.put_object(doc.bucket, doc.storage_path, b"wrong size data", doc.mime_type)
    r_bad_size = client.post(f"/api/v1/documents/{doc_id}/confirm", headers=org.student_headers)
    assert r_bad_size.status_code == 400
    assert not store.object_exists(doc.bucket, doc.storage_path)

    # 3. Content type mismatch -> deleted and 400
    store.put_object(doc.bucket, doc.storage_path, b"x" * 100, "text/plain")
    r_bad_type = client.post(f"/api/v1/documents/{doc_id}/confirm", headers=org.student_headers)
    assert r_bad_type.status_code == 400
    assert not store.object_exists(doc.bucket, doc.storage_path)

    # 4. Correct upload -> 200
    store.put_object(doc.bucket, doc.storage_path, b"x" * 100, "application/pdf")
    r_good = client.post(f"/api/v1/documents/{doc_id}/confirm", headers=org.student_headers)
    assert r_good.status_code == 200

    # 5. Repeat confirm is idempotent no-op
    r_repeat = client.post(f"/api/v1/documents/{doc_id}/confirm", headers=org.student_headers)
    assert r_repeat.status_code == 200


def test_svg_xml_rejected_by_upload_intent(client, org):
    r = client.post(
        "/api/v1/documents/upload-intent",
        json={"filename": "evil.svg", "mime_type": "image/svg+xml", "size_bytes": 100},
        headers=org.student_headers,
    )
    assert r.status_code == 400
    assert "MIME type" in r.text
