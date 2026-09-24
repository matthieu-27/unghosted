"""Pydantic wire models for mail endpoints (us-5)."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field

from unghosted.schemas.projects import StrictModel

# One pragmatic address check instead of the email-validator dependency:
# the tracker's email cells are plain strings too, so the wire format does
# not promise more than the product enforces.
_EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

Language = Literal["fr", "en"]


class MailWarning(StrictModel):
    """One grounding warning recomputed server-side (us-5 item 3)."""

    code: str
    message: str


class LetterDraftBody(StrictModel):
    """POST body for the customised-letter draft (us-5 item 2)."""

    contact_name: str | None = None
    language: Language | None = None


class FirstContactDraftBody(StrictModel):
    """POST body for the first-contact draft (us-5 item 3). The recipient
    is typed manually: no contact records exist before post-MVP."""

    recipient: str = Field(pattern=_EMAIL_PATTERN)
    contact_name: str | None = None
    language: Language | None = None


class DraftUpdateBody(StrictModel):
    """PATCH body for a draft. Absent or null keeps the stored value — the
    wire format has no null-means-clear case."""

    recipient: str | None = Field(default=None, pattern=_EMAIL_PATTERN)
    contact_name: str | None = None
    subject: str | None = Field(default=None, min_length=1)
    text: str | None = Field(default=None, min_length=1)
    attachment_document_ids: list[uuid.UUID] | None = None


class SendBody(StrictModel):
    """POST body for the one-click send. ``sender`` overrides the configured
    From address (MVP: the demo identity)."""

    sender: str | None = Field(default=None, pattern=_EMAIL_PATTERN)


class DraftRead(BaseModel):
    id: uuid.UUID
    kind: str
    status: str
    row_id: str
    recipient: str | None
    contact_name: str | None
    subject: str | None
    text: str | None
    used_highlights: list[str]
    attachment_document_ids: list[uuid.UUID]
    letter_document_id: uuid.UUID | None
    warnings: list[MailWarning]
    created_at: str
    updated_at: str


class ApprovedLetterRead(BaseModel):
    """Letter-approval result (us-5 item 2): the stored PDF document plus
    the one-page verdict the editor warns with."""

    draft: DraftRead
    document_id: uuid.UUID
    fits_one_page: bool


class SentEmailRead(BaseModel):
    """Send result (us-5 items 4 to 6): what went out and the row revision
    the client should adopt."""

    message_id: uuid.UUID
    thread_id: uuid.UUID
    draft_id: uuid.UUID
    sender: str
    recipient: str
    subject: str
    provider: str
    provider_message_id: str | None
    provider_thread_id: str | None
    attachment_document_ids: list[uuid.UUID]
    sent_at: str
    row_revision: int


class SentMessageRead(BaseModel):
    """One recorded sent email (us-5 item 6)."""

    id: uuid.UUID
    thread_id: uuid.UUID
    row_id: str | None
    sender: str
    recipient: str
    subject: str
    direction: str
    provider: str
    provider_message_id: str | None
    attachment_document_ids: list[uuid.UUID]
    sent_at: str
    text: str | None


class SentMessageList(BaseModel):
    data: list[SentMessageRead]
