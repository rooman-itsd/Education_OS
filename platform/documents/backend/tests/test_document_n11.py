"""Regression tests for Security Review Finding N11 in platform/documents."""

from __future__ import annotations

import base64
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml
from eos_core.db import SessionLocal
from eos_core.events import OutboxEvent
from eos_core.tenant import organisation_scope
from eos_documents.application import consumers, service
from eos_documents.domain.models import STATUS_DELETED, STATUS_PENDING_UPLOAD
from eos_documents.infrastructure.config import DocumentsSettings
from eos_documents.infrastructure.storage import MemoryStorage, MinioStorage
from eos_identity.application.service import create_user
from sqlalchemy import select

MODULE_DIR = Path(__file__).resolve().parents[2]


@dataclass
class FakeEvent:
    name: str
    organisation_id: str | None
    payload: dict[str, Any] | None


def test_upload_intent_signs_content_type_and_length_range_into_minio_post_policy(client, org):
    settings = DocumentsSettings(
        storage_backend="minio",
        minio_endpoint="localhost:9000",
        minio_access_key="minioadmin",
        minio_secret_key="minioadmin",
        minio_secure=False,
        minio_bucket="eos-test",
        max_file_size_bytes=1000000,
        url_expires_seconds=900,
    )
    minio_store = MinioStorage(settings)
    url, fields = minio_store.generate_upload_post(
        "eos-test",
        "org-1/uploads/doc-1/u-1",
        "application/pdf",
        4096,
        4096,
        expires_seconds=900,
    )
    assert url == "http://localhost:9000/eos-test"
    assert fields["key"] == "org-1/uploads/doc-1/u-1"
    assert fields["Content-Type"] == "application/pdf"
    assert "x-amz-signature" in fields
    policy = json.loads(base64.b64decode(fields["policy"]).decode("utf-8"))
    assert ["eq", "$Content-Type", "application/pdf"] in policy["conditions"]
    assert ["content-length-range", 4096, 4096] in policy["conditions"]

    r = client.post(
        "/api/v1/documents/upload-intent",
        json={"filename": "lab.pdf", "mime_type": "application/pdf", "size_bytes": 100},
        headers=org.student_headers,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["method"] == "POST"
    assert body["upload_fields"]["Content-Type"] == "application/pdf"
    assert body["upload_fields"]["min_size_bytes"] == "100"
    assert body["upload_fields"]["max_size_bytes"] == "100"


def test_sweep_pending_uploads_cleans_stale_objects_and_blanks_metadata(db, org, monkeypatch):
    from eos_documents.application import jobs

    storage = MemoryStorage()
    monkeypatch.setattr("eos_documents.application.service.get_storage", lambda cfg=None: storage)
    monkeypatch.setattr("eos_documents.application.consumers.get_storage", lambda cfg=None: storage)

    stale_doc, _, _, _ = service.request_upload_intent(
        db,
        org.id,
        actor_id=org.student_id,
        filename="abandoned_big_file.pdf",
        mime_type="application/pdf",
        size_bytes=1024,
        title="Abandoned Upload",
        storage=storage,
    )
    fresh_doc, _, _, _ = service.request_upload_intent(
        db,
        org.id,
        actor_id=org.student_id,
        filename="fresh_file.pdf",
        mime_type="application/pdf",
        size_bytes=512,
        title="Fresh Upload",
        storage=storage,
    )
    stale_doc.created_at = datetime.now(UTC) - timedelta(hours=3)
    db.commit()

    stale_key = stale_doc.upload_path
    fresh_key = fresh_doc.upload_path
    storage.put_object(stale_doc.bucket, stale_key, b"x" * 1024, "application/pdf")
    storage.put_object(fresh_doc.bucket, fresh_key, b"y" * 512, "application/pdf")

    run_id = str(uuid.uuid4())
    consumers.CONSUMERS["scheduler.job.due"](
        db,
        FakeEvent(
            name="scheduler.job.due",
            organisation_id=None,
            payload={"job": jobs.SWEEP_PENDING, "run_id": run_id},
        ),
    )
    db.commit()

    assert not storage.object_exists(stale_doc.bucket, stale_key)
    assert storage.object_exists(fresh_doc.bucket, fresh_key)

    with organisation_scope(org.id), SessionLocal() as s:
        s_stale = service.get_document(s, org.id, stale_doc.id)
        s_fresh = service.get_document(s, org.id, fresh_doc.id)
        assert s_stale.status == STATUS_DELETED
        assert s_stale.filename == ""
        assert s_stale.title == ""
        assert s_fresh.status == STATUS_PENDING_UPLOAD
        assert s_fresh.filename == "fresh_file.pdf"

    evs = list(db.execute(select(OutboxEvent).where(OutboxEvent.name == "documents.job.finished")).scalars().all())
    assert len(evs) == 1 and evs[0].payload["outcome"] == "succeeded"


def test_deleted_document_blanks_filename_and_title_in_status_deleted_list(client, org, db):
    doc = service.direct_upload(
        db,
        org.id,
        org.faculty_id,
        "confidential_salary_2026.pdf",
        "application/pdf",
        b"secret-pdf",
        title="Executive Salaries",
    )
    db.commit()

    r_del = client.delete(f"/api/v1/documents/{doc.id}", headers=org.admin_headers)
    assert r_del.status_code == 200

    r_list = client.get("/api/v1/documents/?status=deleted", headers=org.admin_headers)
    assert r_list.status_code == 200
    items = r_list.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == doc.id
    assert items[0]["filename"] == ""
    assert items[0]["title"] == ""


def test_department_admin_does_not_hold_org_wide_read_any(client, org, db):
    perms = yaml.safe_load((MODULE_DIR / "contracts" / "permissions.yaml").read_text())
    dept_role = next(r for r in perms["roles"] if r["name"] == "department-admin")
    assert "documents:document:read-any" not in dept_role["grants"]

    doc = service.direct_upload(
        db,
        org.id,
        org.student_id,
        "student_medical.pdf",
        "application/pdf",
        b"private",
    )
    db.commit()

    with organisation_scope(org.id):
        dept_user = create_user(
            db,
            organisation_id=org.id,
            email=f"dept-{uuid.uuid4().hex[:8]}@example.com",
            name="dept",
            password="Secret123!",
            roles=["department-admin"],
        )
        db.commit()
    dept_headers = org.auth_headers(dept_user)
    r_list = client.get("/api/v1/documents/", headers=dept_headers)
    assert r_list.status_code == 200, r_list.text
    assert r_list.json()["total"] == 0
    assert client.get(f"/api/v1/documents/{doc.id}", headers=dept_headers).status_code == 404
