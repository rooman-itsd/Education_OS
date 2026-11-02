"""Request bodies of contracts/openapi.yaml. Strict: unknown fields are refused, except readOnly fields of a schema
that is both input and output, which are accepted and ignored. Lengths match the columns, so an over-long value is
422 before it reaches the database."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Priority = Literal["normal", "urgent", "immediate"]
Mode = Literal["email", "post", "courier", "by_hand"]
ID = {"min_length": 1, "max_length": 36}
EMAIL = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CategoryInput(Strict):
    id: str | None = None  # readOnly fields of Category, accepted and ignored
    organisation_id: str | None = None
    code: str = Field(min_length=2, max_length=20)
    name: str = Field(min_length=1, max_length=200)
    retention_years: int | None = Field(default=None, ge=0, le=1000)
    active: bool | None = None


class FileInput(Strict):
    subject: str = Field(min_length=1, max_length=500)
    category_id: str = Field(**ID)
    department_id: str | None = Field(default=None, max_length=36)
    priority: Priority = "normal"
    confidential: bool = False
    first_note: str | None = Field(default=None, max_length=20000)
    receipt_id: str | None = Field(default=None, max_length=36)


class NoteInput(Strict):
    text: str = Field(min_length=1, max_length=20000)
    attachment_ids: list[str] = Field(default_factory=list, max_length=100)


class AttachmentInput(Strict):
    document_id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=300)
    kind: Literal["correspondence", "draft", "order", "reference", "other"] = "reference"


class ForwardInput(Strict):
    to_user_id: str = Field(**ID)
    remark: str | None = Field(default=None, max_length=5000)
    action_required: str | None = Field(default=None, max_length=200)
    due_on: date | None = None


class DecisionInput(Strict):
    decision: Literal["approved", "rejected", "returned"]
    remark: str = Field(min_length=1, max_length=20000)
    forward_to_user_id: str | None = Field(default=None, max_length=36)


class RemarkInput(Strict):
    remark: str = Field(min_length=1, max_length=5000)


class ReceiptInput(Strict):
    received_on: date
    sender: str = Field(min_length=1, max_length=300)
    sender_reference: str | None = Field(default=None, max_length=200)
    subject: str = Field(min_length=1, max_length=500)
    mode: Mode | None = None
    document_id: str | None = Field(default=None, max_length=100)
    send_to_user_id: str = Field(**ID)


class AttachReceiptInput(Strict):
    file_id: str = Field(**ID)


class DispatchInput(Strict):
    file_id: str = Field(**ID)
    attachment_id: str = Field(**ID)
    addressee: str = Field(min_length=1, max_length=300)
    address: str | None = Field(default=None, max_length=2000)
    email: str | None = Field(default=None, max_length=254, pattern=EMAIL)


class MarkSentInput(Strict):
    mode: Mode
    sent_on: date
    reference: str | None = Field(default=None, max_length=200)


def dump(model: BaseModel) -> dict:
    return model.model_dump()
