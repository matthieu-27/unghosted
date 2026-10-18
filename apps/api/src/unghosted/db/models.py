"""SQLAlchemy ORM models (app schema).

No ``from __future__ import annotations``: SQLAlchemy resolves ``Mapped[...]``
at class-creation time, and Python 3.14 defers evaluation natively anyway.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Shared declarative base; Alembic autogenerate reads its metadata."""


class Project(Base):
    __tablename__ = "projects"
    # RUF012 noqa: SQLAlchemy declares __table_args__ as an instance attribute
    # on DeclarativeBase, so ClassVar would break mypy. The dict is read-only config.
    __table_args__: Any = {"schema": "app"}  # noqa: RUF012

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    template_key: Mapped[str] = mapped_column(String, nullable=False)
    template_version: Mapped[int] = mapped_column(Integer, nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class LinkAnalysis(Base):
    __tablename__ = "link_analyses"
    __table_args__: Any = {"schema": "app"}  # noqa: RUF012 — see Project

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("app.projects.id"), nullable=False, index=True
    )
    requested_by: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    input_type: Mapped[str] = mapped_column(String, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    page_kind: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="ok")
    provider: Mapped[str | None] = mapped_column(String, nullable=True)
    timings_ms: Mapped[dict[str, object]] = mapped_column(
        postgresql.JSONB, nullable=False, default=dict
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    cleaned_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_output: Mapped[dict[str, object]] = mapped_column(
        postgresql.JSONB, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class Document(Base):
    __tablename__ = "documents"
    # RUF012 noqa: SQLAlchemy declares __table_args__ as an instance attribute
    # on DeclarativeBase, so ClassVar would break mypy. The dict is read-only config.
    __table_args__: Any = (
        UniqueConstraint("project_id", "storage_key"),
        {"schema": "app"},
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("app.projects.id"), nullable=False, index=True
    )
    type_key: Mapped[str] = mapped_column(String, nullable=False)
    model_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False)
    """Eligibility snapshot at upload (ADR 0009): a later template change
    never retroactively exposes old documents."""
    storage_key: Mapped[str] = mapped_column(String, nullable=False)
    encrypted_data_key: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    key_algorithm_version: Mapped[str] = mapped_column(String, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String, nullable=False)
    original_filename: Mapped[str] = mapped_column(String, nullable=False)
    retention_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class DocumentText(Base):
    __tablename__ = "document_texts"
    __table_args__: Any = {"schema": "app"}  # noqa: RUF012 — see Project

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("app.documents.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class ApplicantProfile(Base):
    __tablename__ = "applicant_profiles"
    __table_args__: Any = (
        UniqueConstraint("project_id", "version_number"),
        {"schema": "app"},
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("app.projects.id"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="draft")
    """draft | approved | superseded (us-4: regenerating never overwrites an
    approved version — approval moves the flag, history stays)."""
    headline: Mapped[str | None] = mapped_column(Text, nullable=True)
    seeking: Mapped[str | None] = mapped_column(Text, nullable=True)
    highlights: Mapped[list[dict[str, object]]] = mapped_column(
        postgresql.JSONB, nullable=False, default=list
    )
    motivation: Mapped[str | None] = mapped_column(Text, nullable=True)
    style_notes: Mapped[list[dict[str, object]]] = mapped_column(
        postgresql.JSONB, nullable=False, default=list
    )
    availability: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class Consent(Base):
    __tablename__ = "consents"
    __table_args__: Any = (
        UniqueConstraint("user_id", "kind"),
        {"schema": "app"},
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    """What the consent covers. MVP: model_processing (us-4 item 5).
    Post-MVP: mailbox providers land here too."""
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    withdrawn_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class MailDraft(Base):
    __tablename__ = "mail_drafts"
    __table_args__: Any = {"schema": "app"}  # noqa: RUF012 — see Project

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("app.projects.id"), nullable=False, index=True
    )
    row_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    """Tracker row id (Mongo). Not a foreign key: Mongo owns row identity."""
    kind: Mapped[str] = mapped_column(String, nullable=False)
    """customised_letter | first_contact_email (us-5 items 2 and 3)."""
    status: Mapped[str] = mapped_column(String, nullable=False, default="draft")
    """draft | approved | sent | discarded."""
    recipient: Mapped[str | None] = mapped_column(Text, nullable=True)
    contact_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    subject: Mapped[str | None] = mapped_column(Text, nullable=True)
    """Set for first-contact emails; letters carry no subject."""
    used_highlights: Mapped[list[str]] = mapped_column(
        postgresql.JSONB, nullable=False, default=list
    )
    """Profile-highlight ids the model relied on — grounding checks verify
    they still exist when the draft is read (us-5 item 3)."""
    attachment_document_ids: Mapped[list[str]] = mapped_column(
        postgresql.JSONB, nullable=False, default=list
    )
    letter_document_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    """Documents row of the approved, rendered letter (us-5 item 2)."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class EmailThread(Base):
    __tablename__ = "email_threads"
    __table_args__: Any = (
        UniqueConstraint("project_id", "recipient"),
        {"schema": "app"},
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("app.projects.id"), nullable=False, index=True
    )
    recipient: Mapped[str] = mapped_column(Text, nullable=False)
    """One thread per project + recipient: follow-ups (post-MVP) attach to
    it with correct headers (us-5 item 5)."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class EmailMessage(Base):
    __tablename__ = "email_messages"
    __table_args__: Any = {"schema": "app"}  # noqa: RUF012 — see Project

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("app.projects.id"), nullable=False, index=True
    )
    thread_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("app.email_threads.id"), nullable=False, index=True
    )
    draft_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    """The sent draft's id — no FK: the draft row is the proposal, the
    message row is the record of what actually went out."""
    row_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    sender: Mapped[str] = mapped_column(Text, nullable=False)
    recipient: Mapped[str] = mapped_column(Text, nullable=False)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    direction: Mapped[str] = mapped_column(String, nullable=False, default="outbound")
    provider: Mapped[str] = mapped_column(String, nullable=False, default="smtp")
    provider_message_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_thread_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    attachment_document_ids: Mapped[list[str]] = mapped_column(
        postgresql.JSONB, nullable=False, default=list
    )
    """Sent documents recorded on the message (us-5 item 6)."""
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__: Any = {"schema": "app"}  # noqa: RUF012 — see Project

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("app.projects.id"), nullable=True, index=True
    )
    kind: Mapped[str] = mapped_column(String, nullable=False)
    """Event name, e.g. email_sent (us-5 item 6)."""
    detail: Mapped[dict[str, object]] = mapped_column(
        postgresql.JSONB, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    """Append-only: audit rows are never updated, so no updated_at."""
