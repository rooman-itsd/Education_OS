"""The two platform services this adapter reaches: platform/documents (store a file, read one back) and
platform/notification (an email with a time-limited download link). integration-hub hands the adapter the real
clients through packages/sdk; until it does, the in-memory ones serve mock mode and the tests, so the adapter is
testable alone (module standard)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class StoredDocument:
    document_id: str
    filename: str
    content_type: str
    content: bytes


class DocumentStore(Protocol):
    def put(self, organisation_id: str, *, filename: str, content_type: str, content: bytes) -> str:
        """Store a file and return its document id."""
        ...

    def get(self, organisation_id: str, document_id: str) -> StoredDocument | None:
        """The document, or None when this organisation has no such document."""
        ...


class CourierError(Exception):
    """Notification could not take the message. `retryable` says whether trying again can help."""

    def __init__(self, retryable: bool = True) -> None:
        super().__init__("courier failed")
        self.retryable = retryable


class Courier(Protocol):
    def send_email_with_link(
        self, organisation_id: str, *, to: str, subject: str, message: str, document_id: str, expires_in_hours: int
    ) -> str:
        """Email `to` a download link for the document that expires after `expires_in_hours`; return a reference.
        Raises CourierError when the message cannot be sent."""
        ...


class MemoryDocumentStore:
    def __init__(self) -> None:
        self._docs: dict[tuple[str, str], StoredDocument] = {}

    def put(self, organisation_id: str, *, filename: str, content_type: str, content: bytes) -> str:
        document_id = str(uuid.uuid4())
        self._docs[(organisation_id, document_id)] = StoredDocument(document_id, filename, content_type, content)
        return document_id

    def get(self, organisation_id: str, document_id: str) -> StoredDocument | None:
        return self._docs.get((organisation_id, document_id))


class MemoryCourier:
    """Records what would have been sent. Mock mode and tests only."""

    def __init__(self) -> None:
        self.sent: list[dict] = []
        self.fail: CourierError | None = None

    def send_email_with_link(
        self, organisation_id: str, *, to: str, subject: str, message: str, document_id: str, expires_in_hours: int
    ) -> str:
        if self.fail:
            raise self.fail
        self.sent.append(
            {
                "organisation_id": organisation_id,
                "to": to,
                "subject": subject,
                "message": message,
                "document_id": document_id,
                "expires_in_hours": expires_in_hours,
            }
        )
        return f"mock-{len(self.sent):06d}"
