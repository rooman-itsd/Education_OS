"""platform/documents as this adapter sees it: store a file, read one back, check one exists, always for one
organisation. integration-hub hands the adapter the real client (through packages/sdk); until that exists the
in-memory store serves mock mode and the tests, so the adapter is testable alone (module standard)."""

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


class MemoryDocumentStore:
    def __init__(self) -> None:
        self._docs: dict[tuple[str, str], StoredDocument] = {}

    def put(self, organisation_id: str, *, filename: str, content_type: str, content: bytes) -> str:
        document_id = str(uuid.uuid4())
        self._docs[(organisation_id, document_id)] = StoredDocument(document_id, filename, content_type, content)
        return document_id

    def get(self, organisation_id: str, document_id: str) -> StoredDocument | None:
        return self._docs.get((organisation_id, document_id))
