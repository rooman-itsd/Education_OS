"""Application services and use cases for student-information."""

from __future__ import annotations

from .service import (
    Actor,
    ServiceError,
    attach_document,
    change_status,
    create_person,
    delete_document,
    get_person,
    get_status_history,
    issue_id_card,
    list_documents,
    list_id_cards,
    list_people,
    revoke_id_card,
    update_person,
)

__all__ = [
    "Actor",
    "ServiceError",
    "attach_document",
    "change_status",
    "create_person",
    "delete_document",
    "get_person",
    "get_status_history",
    "issue_id_card",
    "list_documents",
    "list_id_cards",
    "list_people",
    "revoke_id_card",
    "update_person",
]
