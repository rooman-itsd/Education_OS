"""platform/documents as the adapter needs it. The SDK has no documents client yet (packages/sdk), so the adapter
depends on this narrow protocol, and the hub or the host injects the real one. The in-memory store serves mock
mode and the tests."""

from __future__ import annotations

import hashlib
import uuid
from typing import Protocol


class DocumentStore(Protocol):
    def get(self, organisation_id: str, document_id: str) -> bytes | None: ...

    def put(self, organisation_id: str, *, filename: str, content_type: str, content: bytes) -> str: ...


class InMemoryDocuments:
    def __init__(self) -> None:
        self.files: dict[tuple[str, str], bytes] = {}
        self.meta: dict[str, dict] = {}

    def add(self, organisation_id: str, content: bytes, document_id: str | None = None) -> tuple[str, str]:
        document_id = document_id or str(uuid.uuid4())
        self.files[(organisation_id, document_id)] = content
        return document_id, hashlib.sha256(content).hexdigest()

    def get(self, organisation_id: str, document_id: str) -> bytes | None:
        return self.files.get((organisation_id, document_id))

    def put(self, organisation_id: str, *, filename: str, content_type: str, content: bytes) -> str:
        document_id, _ = self.add(organisation_id, content)
        self.meta[document_id] = {"filename": filename, "content_type": content_type}
        return document_id
