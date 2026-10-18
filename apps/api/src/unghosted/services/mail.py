"""Mail service: draft, edit, approve, send (us-5).

Ownership flows through ProjectRepository.get, same as every other service.
Model output is never trusted: grounding warnings are recomputed server-side
on every read, and the user's explicit click is the only thing that sends.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from unghosted.domain.documents import (
    MAX_DOCUMENT_BYTES,
    checksum_sha256,
    validate_type_key,
)
from unghosted.domain.mail import (
    DRAFT_STATUS,
    FIRST_CONTACT_KIND,
    LETTER_KIND,
    MAX_MAIL_ATTACHMENT_BYTES,
    assert_send_allowed,
    attachment_document_ids,
    day_start,
    detect_language,
    letter_html,
    own_links_from_text,
    today_value,
    validate_grounding,
)
from unghosted.gateways.mail import Attachment, OutgoingMail
from unghosted.gateways.model import (
    FirstContactDraftTask,
    LetterDraftTask,
    ModelUnavailableError,
)
from unghosted.repositories.tracker import StaleRevisionError
from unghosted.services.consents import require_model_consent
from unghosted.services.documents import store_document

if TYPE_CHECKING:
    from collections.abc import Sequence

    from unghosted.db.models import (
        ApplicantProfile,
        Document,
        EmailMessage,
        MailDraft,
        Project,
    )
    from unghosted.domain.templates import Template
    from unghosted.gateways.encrypt import EnvelopeEncryptor
    from unghosted.gateways.mail import MailGateway
    from unghosted.gateways.model import ModelGateway
    from unghosted.gateways.pdf import PdfGateway
    from unghosted.gateways.storage import StorageGateway
    from unghosted.repositories.consents import ConsentRepository
    from unghosted.repositories.documents import (
        DocumentRepository,
        DocumentTextRepository,
    )
    from unghosted.repositories.link_analyses import LinkAnalysisRepository
    from unghosted.repositories.mail import (
        AuditEventRepository,
        EmailContentRepository,
        EmailMessageRepository,
        EmailThreadRepository,
        MailDraftRepository,
    )
    from unghosted.repositories.profiles import ApplicantProfileRepository
    from unghosted.repositories.projects import ProjectRepository
    from unghosted.services.tracker import TrackerService

LETTER_DOCUMENT_TYPE = "generated_customised_letter"
CV_DOCUMENT_TYPE = "cv"
MOTIVATION_LETTER_TYPE = "motivation_letter"

_FRENCH_MONTHS = (
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
)


class NoApprovedProfileError(ValueError):
    """Mail drafting grounds on the approved profile (us-5 items 2–3): no
    approved version means no draft, never a guess."""


class NoListingTextError(ValueError):
    """The row's listing was never analyzed: the letter has nothing to be
    customised against. Run link analysis on the listing_url first (us-3)."""


class RowNotFoundError(LookupError):
    """No tracker row with this id in this project."""


class DraftStateError(ValueError):
    """The operation does not apply to this draft's kind or status."""


class MailValidationError(ValueError):
    """The draft content fails a send-time check (attachment size, missing
    subject or recipient)."""


class RowUpdateFailedError(RuntimeError):
    """The email went out but the tracker row could not be updated: the
    tracker changed while sending. The user reconciles manually."""


@dataclass(frozen=True)
class _DraftContext:
    """Everything both drafting tasks share: the row's cells, the approved
    profile, the stored listing text."""

    project: Project
    row_id: str
    cells: dict[str, Any]
    profile: ApplicantProfile
    listing_text: str


@dataclass(frozen=True)
class MailDraftView:
    id: str
    kind: str
    status: str
    row_id: str
    recipient: str | None
    contact_name: str | None
    subject: str | None
    text: str | None
    used_highlights: list[str]
    attachment_document_ids: list[str]
    letter_document_id: str | None
    warnings: list[dict[str, str]]
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class ApprovedLetterView:
    draft: MailDraftView
    document_id: str
    fits_one_page: bool


@dataclass(frozen=True)
class SentEmailView:
    message_id: str
    thread_id: str
    draft_id: str
    sender: str
    recipient: str
    subject: str
    provider: str
    provider_message_id: str | None
    provider_thread_id: str | None
    attachment_document_ids: list[str]
    sent_at: str
    row_revision: int


@dataclass(frozen=True)
class SentMessageView:
    id: str
    thread_id: str
    row_id: str | None
    sender: str
    recipient: str
    subject: str
    direction: str
    provider: str
    provider_message_id: str | None
    attachment_document_ids: list[str]
    sent_at: str
    text: str | None


def _cell_str(cells: dict[str, Any], key: str) -> str | None:
    value = cells.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _highlight_ids(raw: object) -> list[str]:
    if not isinstance(raw, list):
        return []
    return [str(item) for item in raw if isinstance(item, (str, int))]


def _style_note_texts(profile: ApplicantProfile) -> list[str]:
    texts = []
    for note in profile.style_notes:
        if isinstance(note, dict) and isinstance(note.get("text"), str):
            texts.append(str(note["text"]))
    return texts


def _profile_for_model(profile: ApplicantProfile) -> dict[str, Any]:
    return {
        "headline": profile.headline,
        "seeking": profile.seeking,
        "motivation": profile.motivation,
        "availability": profile.availability,
        "highlights": profile.highlights,
        "style_notes": profile.style_notes,
    }


def _known_highlight_ids(profile: ApplicantProfile) -> list[str]:
    ids = []
    for highlight in profile.highlights:
        if isinstance(highlight, dict) and "id" in highlight:
            ids.append(str(highlight["id"]))
    return ids


def _french_date(day: date) -> str:
    return f"{day.day} {_FRENCH_MONTHS[day.month - 1]} {day.year}"


class MailService:
    def __init__(
        self,
        *,
        projects: ProjectRepository,
        tracker: TrackerService,
        analyses: LinkAnalysisRepository,
        documents: DocumentRepository,
        texts: DocumentTextRepository,
        drafts: MailDraftRepository,
        threads: EmailThreadRepository,
        messages: EmailMessageRepository,
        audit: AuditEventRepository,
        contents: EmailContentRepository,
        profiles: ApplicantProfileRepository,
        consents: ConsentRepository,
        storage: StorageGateway,
        encryptor: EnvelopeEncryptor,
        model: ModelGateway | None,
        mail: MailGateway,
        pdf: PdfGateway,
        templates: dict[str, Template],
        mail_from: str,
        daily_send_cap: int,
        zone: ZoneInfo,
    ) -> None:
        self._projects = projects
        self._tracker = tracker
        self._analyses = analyses
        self._documents = documents
        self._texts = texts
        self._drafts = drafts
        self._threads = threads
        self._messages = messages
        self._audit = audit
        self._contents = contents
        self._profiles = profiles
        self._consents = consents
        self._storage = storage
        self._encryptor = encryptor
        self._model = model
        self._mail = mail
        self._pdf = pdf
        self._templates = templates
        self._mail_from = mail_from
        self._daily_send_cap = daily_send_cap
        self._zone = zone

    # --- drafting (us-5 items 2 and 3) ---------------------------------------

    async def draft_letter(
        self,
        project_id: uuid.UUID,
        owner: uuid.UUID,
        *,
        row_id: str,
        contact_name: str | None,
        language: str | None,
    ) -> MailDraftView:
        ctx = await self._draft_context(project_id, owner, row_id)
        await require_model_consent(self._consents, owner, "draft a letter")
        if self._model is None:
            raise ModelUnavailableError(
                "no model provider is configured (missing API key)"
            )
        motivation_letter_text = await self._latest_document_text(
            project_id, MOTIVATION_LETTER_TYPE
        )
        raw = await self._model.draft_letter(
            LetterDraftTask(
                contact_name=contact_name,
                company=_cell_str(ctx.cells, "company"),
                position=_cell_str(ctx.cells, "position"),
                language=language or detect_language(ctx.listing_text) or "fr",
                listing_text=ctx.listing_text,
                profile=_profile_for_model(ctx.profile),
                motivation_letter_text=motivation_letter_text,
            )
        )
        text = raw.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ModelUnavailableError("model returned no letter text")
        draft = await self._drafts.create(
            project_id=project_id,
            row_id=row_id,
            kind=LETTER_KIND,
            recipient=None,
            contact_name=contact_name,
            subject=None,
            used_highlights=_highlight_ids(raw.get("used_highlights")),
        )
        await self._contents.save_draft(
            draft_id=draft.id, project_id=project_id, proposal=text, text=text
        )
        return await self.get_draft(project_id, owner, draft.id)

    async def draft_first_contact(
        self,
        project_id: uuid.UUID,
        owner: uuid.UUID,
        *,
        row_id: str,
        recipient: str,
        contact_name: str | None,
        language: str | None,
    ) -> MailDraftView:
        ctx = await self._draft_context(project_id, owner, row_id)
        await require_model_consent(self._consents, owner, "draft a first contact")
        if self._model is None:
            raise ModelUnavailableError(
                "no model provider is configured (missing API key)"
            )
        letter_document_id = await self._approved_letter_document_id(project_id, row_id)
        raw = await self._model.draft_first_contact(
            FirstContactDraftTask(
                contact_name=contact_name,
                company=_cell_str(ctx.cells, "company"),
                position=_cell_str(ctx.cells, "position"),
                language=language or detect_language(ctx.listing_text) or "fr",
                listing_text=ctx.listing_text,
                profile=_profile_for_model(ctx.profile),
                letter_attached=letter_document_id is not None,
            )
        )
        subject = raw.get("subject")
        body = raw.get("body")
        if not isinstance(body, str) or not body.strip():
            raise ModelUnavailableError("model returned no email body")
        # Template-suggested preselection (us-5 item 4): the latest CV plus
        # the row's approved letter, both visible and removable in the editor.
        preselected = []
        cv_document_id = await self._latest_document_id(project_id, CV_DOCUMENT_TYPE)
        if cv_document_id is not None:
            preselected.append(str(cv_document_id))
        if letter_document_id is not None:
            preselected.append(str(letter_document_id))
        draft = await self._drafts.create(
            project_id=project_id,
            row_id=row_id,
            kind=FIRST_CONTACT_KIND,
            recipient=recipient,
            contact_name=contact_name,
            subject=subject if isinstance(subject, str) else None,
            used_highlights=_highlight_ids(raw.get("used_highlights")),
            attachment_document_ids=preselected,
        )
        await self._contents.save_draft(
            draft_id=draft.id, project_id=project_id, proposal=body, text=body
        )
        return await self.get_draft(project_id, owner, draft.id)

    async def get_draft(
        self, project_id: uuid.UUID, owner: uuid.UUID, draft_id: uuid.UUID
    ) -> MailDraftView:
        await self._projects.get(project_id, owner)
        draft = await self._drafts.get(draft_id, project_id)
        text = await self._contents.get_draft_text(draft.id)
        warnings = await self._warnings(project_id, owner, draft, text or "")
        return _draft_view(draft, text, warnings)

    async def update_draft(
        self,
        project_id: uuid.UUID,
        owner: uuid.UUID,
        draft_id: uuid.UUID,
        *,
        recipient: str | None,
        contact_name: str | None,
        subject: str | None,
        text: str | None,
        attachment_document_ids: list[str] | None,
    ) -> MailDraftView:
        await self._projects.get(project_id, owner)
        draft = await self._drafts.get(draft_id, project_id)
        if draft.status != DRAFT_STATUS:
            raise DraftStateError(
                f"draft is {draft.status}: only a draft can be edited"
            )
        draft = await self._drafts.update_fields(
            draft,
            recipient=recipient,
            contact_name=contact_name,
            subject=subject,
            used_highlights=None,
            attachment_document_ids=attachment_document_ids,
        )
        if text is not None:
            await self._contents.set_draft_text(draft.id, text)
        return await self.get_draft(project_id, owner, draft.id)

    async def discard_draft(
        self, project_id: uuid.UUID, owner: uuid.UUID, draft_id: uuid.UUID
    ) -> MailDraftView:
        await self._projects.get(project_id, owner)
        draft = await self._drafts.get(draft_id, project_id)
        if draft.status != DRAFT_STATUS:
            raise DraftStateError(
                f"draft is {draft.status}: only a draft can be discarded"
            )
        draft = await self._drafts.set_status(
            draft, "discarded", letter_document_id=None
        )
        return await self.get_draft(project_id, owner, draft.id)

    # --- letter approval (us-5 item 2) ----------------------------------------

    async def approve_letter(
        self, project_id: uuid.UUID, owner: uuid.UUID, draft_id: uuid.UUID
    ) -> ApprovedLetterView:
        project = await self._projects.get(project_id, owner)
        draft = await self._drafts.get(draft_id, project_id)
        if draft.kind != LETTER_KIND:
            raise DraftStateError("only a customised letter can be approved")
        if draft.status != DRAFT_STATUS:
            raise DraftStateError(
                f"draft is {draft.status}: only a draft can be approved"
            )
        text = await self._contents.get_draft_text(draft.id)
        if text is None or not text.strip():
            raise DraftStateError("the letter draft has no text to render")
        cells = await self._row_cells(project_id, owner, draft.row_id)
        company = _cell_str(cells, "company") if cells is not None else None
        now = datetime.now(UTC)
        html = letter_html(
            text,
            contact_name=draft.contact_name,
            company=company,
            date_text=_french_date(now.astimezone(self._zone).date()),
        )
        rendered = await self._pdf.render(html)
        if len(rendered.pdf_bytes) > MAX_DOCUMENT_BYTES:
            raise MailValidationError(
                f"rendered letter exceeds the {MAX_DOCUMENT_BYTES}-byte document cap"
            )
        template = self._templates[project.template_key]
        doc_type = validate_type_key(LETTER_DOCUMENT_TYPE, template)
        document_id = uuid.uuid4()
        document = await store_document(
            documents=self._documents,
            texts=self._texts,
            storage=self._storage,
            encryptor=self._encryptor,
            project_id=project_id,
            owner=owner,
            document_id=document_id,
            doc_type=doc_type,
            filename=f"customised-letter-{document_id}.pdf",
            content=rendered.pdf_bytes,
            text=text,
        )
        draft = await self._drafts.set_status(
            draft, "approved", letter_document_id=document.id
        )
        return ApprovedLetterView(
            draft=await self.get_draft(project_id, owner, draft.id),
            document_id=str(document.id),
            fits_one_page=rendered.fits_one_page,
        )

    # --- sending (us-5 items 4 to 6) -------------------------------------------

    async def send_draft(
        self,
        project_id: uuid.UUID,
        owner: uuid.UUID,
        draft_id: uuid.UUID,
        *,
        sender: str | None,
    ) -> SentEmailView:
        await self._projects.get(project_id, owner)
        draft = await self._drafts.get(draft_id, project_id)
        if draft.kind != FIRST_CONTACT_KIND:
            raise DraftStateError(
                "only a first-contact email is sent; the letter travels as an "
                "attachment"
            )
        if draft.status != DRAFT_STATUS:
            raise DraftStateError(f"draft is {draft.status}: it cannot be sent")
        recipient = draft.recipient
        if recipient is None or not recipient.strip():
            raise MailValidationError("set a recipient before sending")
        subject = draft.subject
        if subject is None or not subject.strip():
            raise MailValidationError("set a subject before sending")
        text = await self._contents.get_draft_text(draft.id)
        if text is None or not text.strip():
            raise MailValidationError("the draft has no body text to send")

        attachments, documents = await self._load_attachments(project_id, draft)

        # Domain limits (us-5 item 5) before the gateway: an SMTP relay would
        # happily deliver what the product promised never to allow.
        now = datetime.now(UTC)
        assert_send_allowed(
            sent_today=await self._messages.count_outbound_since(
                project_id, day_start(now, self._zone)
            ),
            daily_cap=self._daily_send_cap,
            recipient_last_sent=await self._messages.last_outbound_to(
                project_id, recipient
            ),
            now=now,
        )

        from_addr = sender.strip() if sender else self._mail_from
        sent = await self._mail.send(
            OutgoingMail(
                sender=from_addr,
                recipient=recipient,
                subject=subject,
                text_body=text,
                attachments=tuple(attachments),
            )
        )
        thread = await self._threads.get_or_create(project_id, recipient)
        message = await self._messages.create(
            project_id=project_id,
            thread_id=thread.id,
            draft_id=draft.id,
            row_id=draft.row_id,
            sender=from_addr,
            recipient=recipient,
            subject=subject,
            provider=sent.provider,
            provider_message_id=sent.message_id,
            provider_thread_id=sent.thread_id,
            attachment_document_ids=[str(d.id) for d in documents],
            sent_at=now,
        )
        # The final sent text is the record (us-5 item 6): the draft stays
        # editable in history only through its own content row.
        await self._contents.save_message(
            message_id=message.id, project_id=project_id, text=text
        )
        await self._drafts.set_status(draft, "sent", letter_document_id=None)
        await self._audit.record(
            user_id=owner,
            project_id=project_id,
            kind="email_sent",
            detail={
                "message_id": str(message.id),
                "recipient": recipient,
                "row_id": draft.row_id,
                "attachment_document_ids": [str(d.id) for d in documents],
            },
        )
        row_revision = await self._apply_row_updates(
            project_id, owner, draft, documents, now
        )
        return SentEmailView(
            message_id=str(message.id),
            thread_id=str(thread.id),
            draft_id=str(draft.id),
            sender=from_addr,
            recipient=recipient,
            subject=subject,
            provider=sent.provider,
            provider_message_id=sent.message_id,
            provider_thread_id=sent.thread_id,
            attachment_document_ids=[str(d.id) for d in documents],
            sent_at=now.isoformat(),
            row_revision=row_revision,
        )

    async def list_messages(
        self, project_id: uuid.UUID, owner: uuid.UUID
    ) -> list[SentMessageView]:
        await self._projects.get(project_id, owner)
        messages: Sequence[EmailMessage] = await self._messages.list_for_project(
            project_id
        )
        texts = await self._contents.get_message_texts([m.id for m in messages])
        return [
            SentMessageView(
                id=str(message.id),
                thread_id=str(message.thread_id),
                row_id=message.row_id,
                sender=message.sender,
                recipient=message.recipient,
                subject=message.subject,
                direction=message.direction,
                provider=message.provider,
                provider_message_id=message.provider_message_id,
                attachment_document_ids=list(message.attachment_document_ids),
                sent_at=message.sent_at.isoformat(),
                text=texts.get(message.id),
            )
            for message in messages
        ]

    # --- internals -------------------------------------------------------------

    async def _row_cells(
        self, project_id: uuid.UUID, owner: uuid.UUID, row_id: str
    ) -> dict[str, Any] | None:
        """The row's cells, or None when the row no longer exists — drafting
        and grounding both need the same lookup."""
        state = await self._tracker.fetch(project_id, owner)
        row = next((r for r in state.rows if str(r["_id"]) == row_id), None)
        return dict(row.get("cells", {})) if row is not None else None

    async def _draft_context(
        self, project_id: uuid.UUID, owner: uuid.UUID, row_id: str
    ) -> _DraftContext:
        project = await self._projects.get(project_id, owner)
        cells = await self._row_cells(project_id, owner, row_id)
        if cells is None:
            raise RowNotFoundError(f"no row {row_id} in this project")
        profile = await self._profiles.get_approved(project_id)
        if profile is None:
            raise NoApprovedProfileError(
                "approve an applicant profile first (us-4 item 3)"
            )
        listing_url = _cell_str(cells, "listing_url")
        analysis = (
            await self._analyses.latest_for_source(project_id, listing_url)
            if listing_url is not None
            else None
        )
        listing_text = analysis.cleaned_text if analysis is not None else None
        if not listing_text:
            raise NoListingTextError(
                "the row has no analyzed listing: run link analysis on its "
                "listing_url first (us-3)"
            )
        return _DraftContext(
            project=project,
            row_id=row_id,
            cells=cells,
            profile=profile,
            listing_text=listing_text,
        )

    async def _latest_document_id(
        self, project_id: uuid.UUID, type_key: str
    ) -> uuid.UUID | None:
        latest = await self._documents.latest_for_type(project_id, type_key)
        return latest.id if latest is not None else None

    async def _latest_document_text(
        self, project_id: uuid.UUID, type_key: str
    ) -> str | None:
        document_id = await self._latest_document_id(project_id, type_key)
        if document_id is None:
            return None
        text_row = await self._texts.get_for_document(document_id)
        return text_row.text if text_row is not None else None

    async def _approved_letter_document_id(
        self, project_id: uuid.UUID, row_id: str
    ) -> uuid.UUID | None:
        letter = await self._drafts.latest_for_row(project_id, row_id, kind=LETTER_KIND)
        if (
            letter is not None
            and letter.status == "approved"
            and letter.letter_document_id is not None
        ):
            return letter.letter_document_id
        return None

    async def _load_attachments(
        self, project_id: uuid.UUID, draft: MailDraft
    ) -> tuple[list[Attachment], list[Document]]:
        """Resolve, download and decrypt the draft's attachments. All
        documents are PDFs by construction (upload sniffs, the letter
        renders), so the mimetype is constant."""
        ids = attachment_document_ids(
            [uuid.UUID(value) for value in draft.attachment_document_ids]
        )
        attachments: list[Attachment] = []
        documents: list[Document] = []
        total = 0
        for document_id in ids:
            document = await self._documents.get(document_id, project_id)
            encrypted = b"".join(
                [chunk async for chunk in self._storage.read(document.storage_key)]
            )
            content = self._encryptor.decrypt(encrypted, document.encrypted_data_key)
            if checksum_sha256(content) != document.checksum_sha256:
                raise MailValidationError(
                    f"checksum mismatch for attachment {document_id}"
                )
            total += len(content)
            if total > MAX_MAIL_ATTACHMENT_BYTES:
                raise MailValidationError(
                    f"attachments exceed the {MAX_MAIL_ATTACHMENT_BYTES}-byte "
                    "provider limit (us-5 item 4)"
                )
            attachments.append(
                Attachment(
                    filename=document.original_filename,
                    content=content,
                    mimetype="application/pdf",
                )
            )
            documents.append(document)
        return attachments, documents

    async def _warnings(
        self,
        project_id: uuid.UUID,
        owner: uuid.UUID,
        draft: MailDraft,
        text: str,
    ) -> list[dict[str, str]]:
        profile = await self._profiles.get_approved(project_id)
        if profile is None:
            # Nothing to ground against: drafting is impossible, so reaching
            # here means a profile existed earlier and was superseded. The
            # editor still opens; warning-free is not the same as grounded.
            return []
        cells = await self._row_cells(project_id, owner, draft.row_id)
        if cells is None:
            cells = {}
        documents: Sequence[Document] = await self._documents.list_for_project(
            project_id
        )
        types = {str(d.id): d.type_key for d in documents}
        letter_attached = any(
            types.get(value) == LETTER_DOCUMENT_TYPE
            for value in draft.attachment_document_ids
        )
        listing_url = _cell_str(cells, "listing_url")
        expected_language = None
        if listing_url is not None:
            analysis = await self._analyses.latest_for_source(project_id, listing_url)
            if analysis is not None and analysis.cleaned_text:
                expected_language = detect_language(analysis.cleaned_text)
        warnings = validate_grounding(
            text=text,
            used_highlights=draft.used_highlights,
            known_highlight_ids=_known_highlight_ids(profile),
            company=_cell_str(cells, "company"),
            contact_name=draft.contact_name,
            expected_language=expected_language,
            own_links=own_links_from_text(
                profile.headline,
                profile.seeking,
                profile.motivation,
                profile.availability,
                *_style_note_texts(profile),
            ),
            letter_attached=letter_attached,
        )
        return [{"code": w.code, "message": w.message} for w in warnings]

    async def _apply_row_updates(
        self,
        project_id: uuid.UUID,
        owner: uuid.UUID,
        draft: MailDraft,
        documents: list[Document],
        now: datetime,
    ) -> int:
        """Record the send on the row (us-5 item 6) through the same
        operation path as a user edit: the mail worker owns no privileged
        writes. One retry on a stale revision — a concurrent edit during a
        send is common, a race surviving two fetches is not."""
        today = today_value(now, self._zone)
        ops: list[dict[str, Any]] = [
            {
                "op": "set_cell",
                "row_id": draft.row_id,
                "column_key": "date_sent",
                "value": today,
            },
            {
                "op": "set_cell",
                "row_id": draft.row_id,
                "column_key": "last_contact",
                "value": today,
            },
        ]
        cv = next((d for d in documents if d.type_key == CV_DOCUMENT_TYPE), None)
        if cv is not None:
            ops.append(
                {
                    "op": "set_cell",
                    "row_id": draft.row_id,
                    "column_key": "cv",
                    "value": [cv.id],
                }
            )
        letter = next(
            (d for d in documents if d.type_key == LETTER_DOCUMENT_TYPE), None
        )
        if letter is not None:
            ops.append(
                {
                    "op": "set_cell",
                    "row_id": draft.row_id,
                    "column_key": "customised_letter",
                    "value": [letter.id],
                }
            )
        attempts = 0
        while True:
            state = await self._tracker.fetch(project_id, owner)
            try:
                result = await self._tracker.apply(
                    project_id,
                    owner,
                    base_revision=state.revision,
                    raw_operations=ops,
                )
                return result.revision
            except StaleRevisionError:
                attempts += 1
                if attempts >= 2:
                    raise RowUpdateFailedError(
                        "the email was sent but the row could not be updated: "
                        "the tracker changed while sending, set date_sent "
                        "manually"
                    ) from None


def _draft_view(
    draft: MailDraft, text: str | None, warnings: list[dict[str, str]]
) -> MailDraftView:
    return MailDraftView(
        id=str(draft.id),
        kind=draft.kind,
        status=draft.status,
        row_id=draft.row_id,
        recipient=draft.recipient,
        contact_name=draft.contact_name,
        subject=draft.subject,
        text=text,
        used_highlights=list(draft.used_highlights),
        attachment_document_ids=list(draft.attachment_document_ids),
        letter_document_id=str(draft.letter_document_id)
        if draft.letter_document_id is not None
        else None,
        warnings=warnings,
        created_at=draft.created_at.isoformat(),
        updated_at=draft.updated_at.isoformat(),
    )
