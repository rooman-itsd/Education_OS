"""Upload replay protection and versions (#317 follow-up).

The audit confirmed a 9-byte PDF could be overwritten with 60 MB of HTML after confirm: a replayed upload intent
handed out a fresh PUT for the document's own key, and the original PUT URL (valid 15 minutes) still named it.
Now each upload goes to a key of its own, confirm moves the validated object to the document's key, and a replay
after confirm is refused. A changed file is a new version instead, with the history kept."""

from __future__ import annotations

from eos_core.db import SessionLocal
from eos_core.tenant import organisation_scope
from eos_documents.application import service

BASE = "/api/v1/documents"
PDF = b"%PDF-1.7 nine"


def _intent(client, headers, *, token=None, data=PDF, filename="id.pdf"):
    body = {"filename": filename, "mime_type": "application/pdf", "size_bytes": len(data)}
    if token:
        body["client_token"] = token
    r = client.post(f"{BASE}/upload-intent", json=body, headers=headers)
    assert r.status_code in (200, 201), r.text
    return r.json()


def _doc(org, doc_id):
    """Read as the organisation (a session of its own), so row-level security allows it on PostgreSQL too."""
    with organisation_scope(org.id), SessionLocal() as s:
        return service.get_document(s, org.id, doc_id)


def _put(db, org, doc_id, data=PDF, mime="application/pdf"):
    doc = _doc(org, doc_id)
    service.get_storage().put_object(doc.bucket, doc.upload_path, data, mime)
    return doc


def _upload(client, db, org, headers, **kw):
    body = _intent(client, headers, **kw)
    doc_id = body["document"]["id"]
    _put(db, org, doc_id, kw.get("data", PDF))
    r = client.post(f"{BASE}/{doc_id}/confirm", headers=headers)
    assert r.status_code == 200, r.text
    return doc_id


def _stored(db, org, doc_id) -> bytes:
    doc = _doc(org, doc_id)
    return service.get_storage().get_object(doc.bucket, doc.storage_path)


def test_the_upload_url_never_names_the_documents_own_key(client, db, org):
    body = _intent(client, org.student_headers)
    doc = _doc(org, body["document"]["id"])
    assert doc.upload_path and doc.upload_path != doc.storage_path
    assert doc.upload_path.startswith(f"{org.id}/uploads/{doc.id}/")
    assert doc.upload_path in body["upload_url"] and doc.storage_path not in body["upload_url"]


def test_confirm_moves_the_validated_upload_to_the_documents_key(client, db, org):
    doc_id = _upload(client, db, org, org.student_headers)
    doc = _doc(org, doc_id)
    store = service.get_storage()
    assert doc.upload_path is None and store.get_object(doc.bucket, doc.storage_path) == PDF
    assert not [k for (_, k) in store.objects if k.startswith(f"{org.id}/uploads/{doc_id}/")]


def test_a_replayed_intent_after_confirm_gets_no_upload_url(client, db, org):
    doc_id = _upload(client, db, org, org.student_headers, token="tok-1")
    r = client.post(
        f"{BASE}/upload-intent",
        json={"filename": "id.pdf", "mime_type": "application/pdf", "size_bytes": len(PDF), "client_token": "tok-1"},
        headers=org.student_headers,
    )
    assert r.status_code == 409 and "upload_url" not in r.text and "versions" in r.text
    assert _stored(db, org, doc_id) == PDF


def test_a_late_put_on_the_old_upload_url_cannot_change_the_confirmed_file(client, db, org):
    """The audit's probe: confirm a small PDF, then PUT 60 MB of HTML through the URL the client still holds."""
    body = _intent(client, org.student_headers)
    doc_id = body["document"]["id"]
    doc = _put(db, org, doc_id)
    old_upload_key = doc.upload_path
    assert client.post(f"{BASE}/{doc_id}/confirm", headers=org.student_headers).status_code == 200

    service.get_storage().put_object(doc.bucket, old_upload_key, b"<html>" + b"x" * 62_914_560, "text/html")
    assert _stored(db, org, doc_id) == PDF
    assert client.get(f"{BASE}/{doc_id}", headers=org.student_headers).json()["size_bytes"] == len(PDF)
    # A second confirm is still a no-op, not a re-validation of whatever now sits on the upload key
    assert client.post(f"{BASE}/{doc_id}/confirm", headers=org.student_headers).status_code == 200
    assert _stored(db, org, doc_id) == PDF


def test_a_row_from_before_upload_path_still_confirms(client, db, org):
    """Pending rows created before the migration uploaded to storage_path; confirm accepts them there."""
    body = _intent(client, org.student_headers)
    with organisation_scope(org.id), SessionLocal() as s:
        doc = service.get_document(s, org.id, body["document"]["id"])
        doc.upload_path = None
        s.commit()
    service.get_storage().put_object(doc.bucket, doc.storage_path, PDF, "application/pdf")
    assert client.post(f"{BASE}/{doc.id}/confirm", headers=org.student_headers).status_code == 200
    assert _stored(db, org, doc.id) == PDF


# --- versions ---------------------------------------------------------------------------------------------------


def _new_version(client, db, org, headers, doc_id, data, token=None):
    body = {"filename": "id-v2.pdf", "mime_type": "application/pdf", "size_bytes": len(data)}
    if token:
        body["client_token"] = token
    r = client.post(f"{BASE}/{doc_id}/versions", json=body, headers=headers)
    return r


def test_a_new_version_supersedes_the_old_one_which_stays_readable(client, db, org):
    v1 = _upload(client, db, org, org.student_headers)
    v2_data = b"%PDF-1.7 second version"
    r = _new_version(client, db, org, org.student_headers, v1, v2_data)
    assert r.status_code == 201, r.text
    v2 = r.json()["document"]
    assert (v2["version"], v2["version_of"], v2["status"]) == (2, v1, "pending_upload")
    _put(db, org, v2["id"], v2_data)
    assert client.post(f"{BASE}/{v2['id']}/confirm", headers=org.student_headers).status_code == 200

    old = client.get(f"{BASE}/{v1}", headers=org.student_headers).json()
    assert old["superseded_by"] == v2["id"]
    assert _stored(db, org, v1) == PDF and _stored(db, org, v2["id"]) == v2_data

    listed = client.get(f"{BASE}/", headers=org.student_headers).json()
    assert [d["id"] for d in listed["items"]] == [v2["id"]]  # one entry per document: its latest version
    everything = client.get(f"{BASE}/?include_superseded=true", headers=org.student_headers).json()
    assert {d["id"] for d in everything["items"]} == {v1, v2["id"]}

    for any_id in (v1, v2["id"]):
        versions = client.get(f"{BASE}/{any_id}/versions", headers=org.student_headers).json()
        assert [d["version"] for d in versions["items"]] == [2, 1]
    assert client.get(f"{BASE}/{v1}/download-url", headers=org.student_headers).status_code == 200


def test_only_the_latest_version_can_be_followed(client, db, org):
    v1 = _upload(client, db, org, org.student_headers)
    v2 = _new_version(client, db, org, org.student_headers, v1, b"%PDF two").json()["document"]["id"]
    _put(db, org, v2, b"%PDF two")
    client.post(f"{BASE}/{v2}/confirm", headers=org.student_headers)
    assert _new_version(client, db, org, org.student_headers, v1, b"%PDF fork").status_code == 409


def test_two_versions_racing_from_one_predecessor_cannot_both_be_confirmed(client, db, org):
    v1 = _upload(client, db, org, org.student_headers)
    a = _new_version(client, db, org, org.student_headers, v1, b"%PDF aaa", token="a").json()["document"]["id"]
    b = _new_version(client, db, org, org.student_headers, v1, b"%PDF bbb", token="b").json()["document"]["id"]
    _put(db, org, a, b"%PDF aaa")
    _put(db, org, b, b"%PDF bbb")
    assert client.post(f"{BASE}/{a}/confirm", headers=org.student_headers).status_code == 200
    assert client.post(f"{BASE}/{b}/confirm", headers=org.student_headers).status_code == 409
    versions = client.get(f"{BASE}/{v1}/versions", headers=org.student_headers).json()["items"]
    assert [(d["id"], d["status"]) for d in versions if d["status"] == "available"] == [
        (a, "available"),
        (v1, "available"),
    ]


def test_only_the_uploader_adds_versions_and_other_users_see_nothing(client, db, org, other_org):
    v1 = _upload(client, db, org, org.student_headers)
    # Another student of the same organisation: not their document, so it does not exist for them
    assert _new_version(client, db, org, org.student2_headers, v1, b"%PDF x").status_code == 404
    assert client.get(f"{BASE}/{v1}/versions", headers=org.student2_headers).status_code == 404
    # An admin may read every version (read-any) but cannot write someone else's document
    assert client.get(f"{BASE}/{v1}/versions", headers=org.admin_headers).status_code == 200
    assert _new_version(client, db, org, org.admin_headers, v1, b"%PDF x").status_code == 403
    # Another organisation sees nothing at all
    assert client.get(f"{BASE}/{v1}/versions", headers=other_org.admin_headers).status_code == 404
    assert _new_version(client, db, org, other_org.admin_headers, v1, b"%PDF x").status_code == 404


def test_a_new_version_intent_is_idempotent_on_its_client_token(client, db, org):
    v1 = _upload(client, db, org, org.student_headers)
    first = _new_version(client, db, org, org.student_headers, v1, b"%PDF two", token="v2-tok")
    again = _new_version(client, db, org, org.student_headers, v1, b"%PDF two", token="v2-tok")
    assert first.status_code == 201 and again.status_code == 200
    assert first.json()["document"]["id"] == again.json()["document"]["id"]
