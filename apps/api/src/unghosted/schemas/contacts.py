"""Pydantic wire models for contact endpoints (us-7, docs/api-contract.md)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from unghosted.schemas.projects import StrictModel


class ContactCreate(StrictModel):
    """POST body. Only the name is mandatory: a listing usually names a
    company long before it names a person's address (us-7 item 1)."""

    name: str = Field(min_length=1)
    role: str | None = None
    organization: str | None = None
    email: str | None = None
    phone: str | None = None
    profile_url: str | None = None
    notes: str | None = None


class ContactUpdate(StrictModel):
    """PATCH body. An absent key keeps the stored value, an explicit null
    clears it — the service reads `model_fields_set` to tell them apart."""

    name: str | None = Field(default=None, min_length=1)
    role: str | None = None
    organization: str | None = None
    email: str | None = None
    phone: str | None = None
    profile_url: str | None = None
    notes: str | None = None


class ContactRead(BaseModel):
    id: uuid.UUID
    name: str
    role: str | None
    organization: str | None
    email: str | None
    phone: str | None
    profile_url: str | None
    notes: str | None
    linked_row_count: int
    created_at: str
    updated_at: str


class ContactList(BaseModel):
    data: list[ContactRead]


class ContactThreadRead(BaseModel):
    id: uuid.UUID
    recipient: str
    message_count: int
    last_message_at: str | None


class ContactDetailRead(BaseModel):
    """The detail panel payload: the contact plus what it is attached to."""

    contact: ContactRead
    linked_row_ids: list[str]
    threads: list[ContactThreadRead]
