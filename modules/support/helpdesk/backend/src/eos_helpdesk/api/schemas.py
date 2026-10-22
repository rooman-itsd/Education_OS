"""Request bodies, mirroring contracts/openapi.yaml components.schemas. Extra fields are refused, so a misspelt field
is a 422, never silently ignored."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

# The contract types ids as format: uuid. Checked here so a bad id is a 422, never a stored row.
Uuid = Annotated[str, Field(pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")]
Priority = Literal["low", "medium", "high", "urgent"]
HoldReason = Literal["waiting_requester", "waiting_third_party", "waiting_internal"]
Channel = Literal["portal", "email", "phone", "walk_in"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


def sent(body: BaseModel) -> dict:
    """Only the fields the caller sent, so PATCH changes only those and an explicit null differs from a missing
    field (AssignInput)."""
    return body.model_dump(exclude_unset=True)


def full(body: BaseModel) -> dict:
    return body.model_dump()


class QueueInput(Strict):
    name: str = Field(min_length=1, max_length=80)
    description: str | None = None
    member_ids: list[Uuid] | None = None
    active: bool = True


class CategoryInput(Strict):
    parent_id: Uuid | None = None
    name: str = Field(min_length=1, max_length=80)
    description: str | None = None
    default_queue_id: Uuid
    default_priority: Priority
    active: bool = True


class TicketInput(Strict):
    category_id: Uuid
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=3)
    attachment_document_ids: list[str] | None = None


class AgentTicketInput(TicketInput):
    requester_id: Uuid
    channel: Channel
    priority: Priority | None = None
    assign_to_me: bool = False


class TicketUpdate(Strict):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    category_id: Uuid | None = None
    priority: Priority | None = None
    reason: str | None = None


class AssignInput(Strict):
    queue_id: Uuid | None = None
    assignee_id: Uuid | None = None


class StatusInput(Strict):
    status: Literal["in_progress", "on_hold"]
    hold_reason: HoldReason | None = None
    note: str | None = None


class ResolveInput(Strict):
    resolution_note: str = Field(min_length=3)


class CancelInput(Strict):
    reason: str = Field(min_length=3)
    duplicate_of: Uuid | None = None


class ConfirmInput(Strict):
    satisfaction_rating: int | None = Field(default=None, ge=1, le=5)
    feedback: str | None = None


class Reason(Strict):
    reason: str = Field(min_length=3)


class CommentInput(Strict):
    body: str = Field(min_length=1)
    attachment_document_ids: list[str] | None = None


class AgentCommentInput(CommentInput):
    visibility: Literal["public", "internal"]


class LinkInput(Strict):
    module: str = Field(min_length=1, max_length=80)
    entity: str = Field(min_length=1, max_length=80)
    ref_id: str = Field(min_length=1, max_length=200)
    note: str | None = None
