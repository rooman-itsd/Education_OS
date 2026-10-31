"""Unit tests for document domain models and file validation policy."""

import pytest
from eos_documents.domain.models import (
    ALLOWED_STATUSES,
    STATUS_AVAILABLE,
    STATUS_DELETED,
    STATUS_PENDING_UPLOAD,
    TABLE_NAMES,
    Document,
    validate_file_policy,
)


def test_table_names_declared():
    assert TABLE_NAMES == ["documents_document"]


def test_document_model_defaults():
    doc = Document(
        organisation_id="org-1",
        title="Student ID Card",
        filename="id_card.pdf",
        mime_type="application/pdf",
        size_bytes=1048576,
        storage_path="org-1/2026/10/doc-1/id_card.pdf",
        bucket="eos-documents",
        uploaded_by="user-1",
    )
    assert doc.status == STATUS_PENDING_UPLOAD
    assert doc.tags == []
    assert doc.title == "Student ID Card"
    assert doc.size_bytes == 1048576


def test_document_allowed_statuses():
    assert STATUS_PENDING_UPLOAD in ALLOWED_STATUSES
    assert STATUS_AVAILABLE in ALLOWED_STATUSES
    assert STATUS_DELETED in ALLOWED_STATUSES


def test_file_policy_valid_files():
    # PDF
    validate_file_policy("syllabus.pdf", "application/pdf", 1024, 10000)
    # JPEG
    validate_file_policy("profile.jpeg", "image/jpeg", 50000, 1000000)
    # PNG
    validate_file_policy("diagram.png", "image/png", 50000, 1000000)
    # DOCX
    validate_file_policy(
        "thesis.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        200000,
        10000000,
    )


def test_file_policy_rejects_dangerous_extensions():
    with pytest.raises(ValueError, match="forbidden for security reasons"):
        validate_file_policy("script.sh", "application/pdf", 1024, 10000)

    with pytest.raises(ValueError, match="forbidden for security reasons"):
        validate_file_policy("malware.exe", "application/pdf", 1024, 10000)

    with pytest.raises(ValueError, match="forbidden for security reasons"):
        validate_file_policy("hack.bat", "application/pdf", 1024, 10000)


def test_file_policy_rejects_unapproved_mime_types():
    with pytest.raises(ValueError, match="MIME type 'audio/mpeg' is not permitted"):
        validate_file_policy("audio.mp3", "audio/mpeg", 1024, 10000)

    with pytest.raises(ValueError, match="MIME type 'video/mp4' is not permitted"):
        validate_file_policy("video.mp4", "video/mp4", 1024, 10000)


def test_file_policy_rejects_invalid_sizes():
    # 0 or negative
    with pytest.raises(ValueError, match="greater than 0 bytes"):
        validate_file_policy("file.pdf", "application/pdf", 0, 10000)

    # Exceeds max limit
    with pytest.raises(ValueError, match="exceeds maximum allowed limit"):
        validate_file_policy("large.pdf", "application/pdf", 15000, 10000)
