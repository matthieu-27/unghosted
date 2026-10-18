"""Mail persistence: drafts, threads, messages, audit (PostgreSQL) and
mail text bodies (MongoDB email_contents, ADR 0001 data split)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from unghosted.db.models import AuditEvent, EmailMessage, EmailThread, MailDraft

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pymongo.asynchronous.collection import AsyncCollection
    from pymongo.asynchronous.database import AsyncDatabase


class MailDraftNotFoundError(LookupError):
    """No draft with this id in this project."""


class MailDraftRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        project_id: uuid.UUID,
        row_id: str,
        kind: str,
        recipient: str | None,
        contact_name: str | None,
        subject: str | None,
        used_highlights: list[str],
        attachment_document_ids: list[str] | None = None,
    ) -> MailDraft:
        draft = MailDraft(
            project_id=project_id,
            row_id=row_id,
            kind=kind,
            recipient=recipient,
            contact_name=contact_name,
            subject=subject,
            used_highlights=used_highlights,
            attachment_document_ids=attachment_document_ids or [],
        )
        self._session.add(draft)
        await self._session.flush()
        await self._session.refresh(draft)
        return draft

    async def get(self, draft_id: uuid.UUID, project_id: uuid.UUID) -> MailDraft:
        draft = await self._session.get(MailDraft, draft_id)
        if draft is None or draft.project_id != project_id:
            raise MailDraftNotFoundError(str(draft_id))
        return draft

    async def update_fields(
        self,
        draft: MailDraft,
        *,
        recipient: str | None,
        contact_name: str | None,
        subject: str | None,
        used_highlights: list[str] | None,
        attachment_document_ids: list[str] | None,
    ) -> MailDraft:
        """Set exactly the fields the request carries; None keeps the stored
        value (PATCH semantics). The wire schema forbids empty strings for
        recipient, subject and text, so those are never clearable — only
        attachment_document_ids accepts [] to mean "none"."""
        if recipient is not None:
            draft.recipient = recipient
        if contact_name is not None:
            draft.contact_name = contact_name
        if subject is not None:
            draft.subject = subject
        if used_highlights is not None:
            draft.used_highlights = used_highlights
        if attachment_document_ids is not None:
            draft.attachment_document_ids = attachment_document_ids
        await self._session.flush()
        await self._session.refresh(draft)
        return draft

    async def set_status(
        self, draft: MailDraft, status: str, *, letter_document_id: uuid.UUID | None
    ) -> MailDraft:
        draft.status = status
        if letter_document_id is not None:
            draft.letter_document_id = letter_document_id
        await self._session.flush()
        await self._session.refresh(draft)
        return draft

    async def list_for_project(self, project_id: uuid.UUID) -> Sequence[MailDraft]:
        stmt = (
            select(MailDraft)
            .where(MailDraft.project_id == project_id)
            .order_by(MailDraft.updated_at.desc())
        )
        return (await self._session.scalars(stmt)).all()

    async def latest_for_row(
        self, project_id: uuid.UUID, row_id: str, *, kind: str
    ) -> MailDraft | None:
        """Most recently touched draft of one kind on one row (us-5): the
        first-contact flow asks whether an approved letter already exists."""
        stmt = (
            select(MailDraft)
            .where(
                MailDraft.project_id == project_id,
                MailDraft.row_id == row_id,
                MailDraft.kind == kind,
            )
            .order_by(MailDraft.updated_at.desc())
            .limit(1)
        )
        return (await self._session.scalars(stmt)).first()


class EmailThreadRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_or_create(self, project_id: uuid.UUID, recipient: str) -> EmailThread:
        stmt = select(EmailThread).where(
            EmailThread.project_id == project_id,
            EmailThread.recipient == recipient,
        )
        thread = (await self._session.scalars(stmt)).first()
        if thread is None:
            thread = EmailThread(project_id=project_id, recipient=recipient)
            self._session.add(thread)
            await self._session.flush()
            await self._session.refresh(thread)
        return thread


class EmailMessageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        project_id: uuid.UUID,
        thread_id: uuid.UUID,
        draft_id: uuid.UUID | None,
        row_id: str | None,
        sender: str,
        recipient: str,
        subject: str,
        provider: str,
        provider_message_id: str | None,
        provider_thread_id: str | None,
        attachment_document_ids: list[str],
        sent_at: datetime,
    ) -> EmailMessage:
        message = EmailMessage(
            project_id=project_id,
            thread_id=thread_id,
            draft_id=draft_id,
            row_id=row_id,
            sender=sender,
            recipient=recipient,
            subject=subject,
            provider=provider,
            provider_message_id=provider_message_id,
            provider_thread_id=provider_thread_id,
            attachment_document_ids=attachment_document_ids,
            sent_at=sent_at,
        )
        self._session.add(message)
        await self._session.flush()
        await self._session.refresh(message)
        return message

    async def count_outbound_since(self, project_id: uuid.UUID, since: datetime) -> int:
        """Sends since the local day start — the daily-cap input (us-5 item
        5). Counts messages, not drafts: only real sends consume the cap."""
        stmt = (
            select(func.count())
            .select_from(EmailMessage)
            .where(
                EmailMessage.project_id == project_id,
                EmailMessage.direction == "outbound",
                EmailMessage.sent_at >= since,
            )
        )
        return int((await self._session.scalar(stmt)) or 0)

    async def last_outbound_to(
        self, project_id: uuid.UUID, recipient: str
    ) -> datetime | None:
        stmt = select(func.max(EmailMessage.sent_at)).where(
            EmailMessage.project_id == project_id,
            EmailMessage.direction == "outbound",
            EmailMessage.recipient == recipient,
        )
        return (await self._session.scalar(stmt)) or None

    async def list_for_project(self, project_id: uuid.UUID) -> Sequence[EmailMessage]:
        stmt = (
            select(EmailMessage)
            .where(EmailMessage.project_id == project_id)
            .order_by(EmailMessage.sent_at.desc())
        )
        return (await self._session.scalars(stmt)).all()


class AuditEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(
        self,
        *,
        user_id: uuid.UUID,
        project_id: uuid.UUID | None,
        kind: str,
        detail: dict[str, object],
    ) -> AuditEvent:
        event = AuditEvent(
            user_id=user_id, project_id=project_id, kind=kind, detail=detail
        )
        self._session.add(event)
        await self._session.flush()
        return event


class EmailContentRepository:
    """Mongo ``email_contents``: mail text never lands in Postgres (ADR 0001
    data split — same rule as document texts vs document_texts)."""

    def __init__(self, db: AsyncDatabase[dict[str, Any]]) -> None:
        self._contents: AsyncCollection[dict[str, Any]] = db.get_collection(
            "email_contents"
        )

    async def save_draft(
        self,
        *,
        draft_id: uuid.UUID,
        project_id: uuid.UUID,
        proposal: str,
        text: str,
    ) -> None:
        await self._contents.update_one(
            {"_id": draft_id},
            {
                "$set": {
                    "project_id": project_id,
                    "kind": "mail_draft",
                    "proposal": proposal,
                    "text": text,
                }
            },
            upsert=True,
        )

    async def set_draft_text(self, draft_id: uuid.UUID, text: str) -> None:
        result = await self._contents.update_one(
            {"_id": draft_id, "kind": "mail_draft"}, {"$set": {"text": text}}
        )
        if result.matched_count == 0:
            raise MailDraftNotFoundError(str(draft_id))

    async def get_draft_text(self, draft_id: uuid.UUID) -> str | None:
        doc = await self._contents.find_one(
            {"_id": draft_id, "kind": "mail_draft"}, {"text": 1}
        )
        if doc is None:
            return None
        text = doc.get("text")
        return str(text) if isinstance(text, str) else None

    async def save_message(
        self,
        *,
        message_id: uuid.UUID,
        project_id: uuid.UUID,
        text: str,
    ) -> None:
        await self._contents.update_one(
            {"_id": message_id},
            {
                "$set": {
                    "project_id": project_id,
                    "kind": "email_message",
                    "text": text,
                }
            },
            upsert=True,
        )

    async def get_message_text(self, message_id: uuid.UUID) -> str | None:
        doc = await self._contents.find_one(
            {"_id": message_id, "kind": "email_message"}, {"text": 1}
        )
        if doc is None:
            return None
        text = doc.get("text")
        return str(text) if isinstance(text, str) else None

    async def get_message_texts(
        self, message_ids: Sequence[uuid.UUID]
    ) -> dict[uuid.UUID, str]:
        """One query for every message text — the list view must not run
        one Mongo read per row."""
        if not message_ids:
            return {}
        cursor = self._contents.find(
            {"_id": {"$in": list(message_ids)}, "kind": "email_message"},
            {"text": 1},
        )
        texts: dict[uuid.UUID, str] = {}
        async for doc in cursor:
            text = doc.get("text")
            if isinstance(text, str):
                texts[doc["_id"]] = text
        return texts
