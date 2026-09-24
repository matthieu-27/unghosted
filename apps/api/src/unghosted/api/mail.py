"""Mail endpoints: letter and first-contact drafts, approve, send (us-5)."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from litestar import Controller, get, patch, post
from litestar.di import NamedDependency
from litestar.exceptions import (
    HTTPException,
    NotFoundException,
    PermissionDeniedException,
    ValidationException,
)
from litestar.params import FromPath
from litestar.status_codes import (
    HTTP_409_CONFLICT,
    HTTP_502_BAD_GATEWAY,
    HTTP_503_SERVICE_UNAVAILABLE,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable

from unghosted.api.strict_dto import StrictPydanticDTO
from unghosted.domain.documents import DocumentValidationError
from unghosted.domain.mail import SendLimitError
from unghosted.gateways.mail import MailSendError
from unghosted.gateways.model import ModelUnavailableError
from unghosted.gateways.pdf import PdfRenderError
from unghosted.repositories.documents import DocumentNotFoundError
from unghosted.repositories.mail import MailDraftNotFoundError
from unghosted.repositories.projects import ProjectNotFoundError
from unghosted.schemas import (
    ApprovedLetterRead,
    DraftRead,
    DraftUpdateBody,
    FirstContactDraftBody,
    LetterDraftBody,
    MailWarning,
    SendBody,
    SentEmailRead,
    SentMessageList,
    SentMessageRead,
)
from unghosted.services.consents import ConsentRequiredError
from unghosted.services.mail import (
    ApprovedLetterView,
    DraftStateError,
    MailDraftView,
    MailService,
    MailValidationError,
    NoApprovedProfileError,
    NoListingTextError,
    RowNotFoundError,
    RowUpdateFailedError,
    SentEmailView,
    SentMessageView,
)


def _not_found(detail: str) -> NotFoundException:
    return NotFoundException(detail=detail, extra={"code": "not_found"})


def _conflict(exc: Exception, code: str) -> HTTPException:
    return HTTPException(
        status_code=HTTP_409_CONFLICT, detail=str(exc), extra={"code": code}
    )


async def _drafting_call(
    project_id: uuid.UUID, call: Awaitable[MailDraftView]
) -> MailDraftView:
    """Run one drafting service call and map its error set to the wire —
    both drafting endpoints raise exactly the same exceptions."""
    try:
        return await call
    except ProjectNotFoundError as exc:
        raise _not_found(f"project {project_id} not found") from exc
    except RowNotFoundError as exc:
        raise _not_found(str(exc)) from exc
    except NoApprovedProfileError as exc:
        raise _conflict(exc, "no_approved_profile") from exc
    except NoListingTextError as exc:
        raise _conflict(exc, "no_listing_text") from exc
    except ConsentRequiredError as exc:
        raise PermissionDeniedException(
            detail=str(exc), extra={"code": "consent_required"}
        ) from exc
    except ModelUnavailableError as exc:
        raise HTTPException(
            status_code=HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
            extra={"code": "model_unavailable"},
        ) from exc


def _draft_read(view: MailDraftView) -> DraftRead:
    return DraftRead(
        id=uuid.UUID(view.id),
        kind=view.kind,
        status=view.status,
        row_id=view.row_id,
        recipient=view.recipient,
        contact_name=view.contact_name,
        subject=view.subject,
        text=view.text,
        used_highlights=view.used_highlights,
        attachment_document_ids=[
            uuid.UUID(value) for value in view.attachment_document_ids
        ],
        letter_document_id=uuid.UUID(view.letter_document_id)
        if view.letter_document_id is not None
        else None,
        warnings=[
            MailWarning(code=w["code"], message=w["message"]) for w in view.warnings
        ],
        created_at=view.created_at,
        updated_at=view.updated_at,
    )


def _approved_read(view: ApprovedLetterView) -> ApprovedLetterRead:
    return ApprovedLetterRead(
        draft=_draft_read(view.draft),
        document_id=uuid.UUID(view.document_id),
        fits_one_page=view.fits_one_page,
    )


def _sent_read(view: SentEmailView) -> SentEmailRead:
    return SentEmailRead(
        message_id=uuid.UUID(view.message_id),
        thread_id=uuid.UUID(view.thread_id),
        draft_id=uuid.UUID(view.draft_id),
        sender=view.sender,
        recipient=view.recipient,
        subject=view.subject,
        provider=view.provider,
        provider_message_id=view.provider_message_id,
        provider_thread_id=view.provider_thread_id,
        attachment_document_ids=[
            uuid.UUID(value) for value in view.attachment_document_ids
        ],
        sent_at=view.sent_at,
        row_revision=view.row_revision,
    )


def _message_read(view: SentMessageView) -> SentMessageRead:
    return SentMessageRead(
        id=uuid.UUID(view.id),
        thread_id=uuid.UUID(view.thread_id),
        row_id=view.row_id,
        sender=view.sender,
        recipient=view.recipient,
        subject=view.subject,
        direction=view.direction,
        provider=view.provider,
        provider_message_id=view.provider_message_id,
        attachment_document_ids=[
            uuid.UUID(value) for value in view.attachment_document_ids
        ],
        sent_at=view.sent_at,
        text=view.text,
    )


class MailController(Controller):
    path = "/projects/{project_id:uuid}"

    @post(
        "/rows/{row_id:str}/letter",
        status_code=200,
        dto=StrictPydanticDTO[LetterDraftBody],
    )
    async def draft_letter(
        self,
        project_id: FromPath[uuid.UUID],
        row_id: FromPath[str],
        data: LetterDraftBody,
        mail_service: NamedDependency[MailService],
        current_user: NamedDependency[uuid.UUID],
    ) -> DraftRead:
        view = await _drafting_call(
            project_id,
            mail_service.draft_letter(
                project_id,
                current_user,
                row_id=row_id,
                contact_name=data.contact_name,
                language=data.language,
            ),
        )
        return _draft_read(view)

    @post(
        "/rows/{row_id:str}/first-contact",
        status_code=200,
        dto=StrictPydanticDTO[FirstContactDraftBody],
    )
    async def draft_first_contact(
        self,
        project_id: FromPath[uuid.UUID],
        row_id: FromPath[str],
        data: FirstContactDraftBody,
        mail_service: NamedDependency[MailService],
        current_user: NamedDependency[uuid.UUID],
    ) -> DraftRead:
        view = await _drafting_call(
            project_id,
            mail_service.draft_first_contact(
                project_id,
                current_user,
                row_id=row_id,
                recipient=data.recipient,
                contact_name=data.contact_name,
                language=data.language,
            ),
        )
        return _draft_read(view)

    @get("/drafts/{draft_id:uuid}")
    async def get_draft(
        self,
        project_id: FromPath[uuid.UUID],
        draft_id: FromPath[uuid.UUID],
        mail_service: NamedDependency[MailService],
        current_user: NamedDependency[uuid.UUID],
    ) -> DraftRead:
        try:
            view = await mail_service.get_draft(project_id, current_user, draft_id)
        except ProjectNotFoundError as exc:
            raise _not_found(f"project {project_id} not found") from exc
        except MailDraftNotFoundError as exc:
            raise _not_found(str(exc)) from exc
        return _draft_read(view)

    @patch("/drafts/{draft_id:uuid}", dto=StrictPydanticDTO[DraftUpdateBody])
    async def update_draft(
        self,
        project_id: FromPath[uuid.UUID],
        draft_id: FromPath[uuid.UUID],
        data: DraftUpdateBody,
        mail_service: NamedDependency[MailService],
        current_user: NamedDependency[uuid.UUID],
    ) -> DraftRead:
        try:
            view = await mail_service.update_draft(
                project_id,
                current_user,
                draft_id,
                recipient=data.recipient,
                contact_name=data.contact_name,
                subject=data.subject,
                text=data.text,
                attachment_document_ids=[str(d) for d in data.attachment_document_ids]
                if data.attachment_document_ids is not None
                else None,
            )
        except (ProjectNotFoundError, MailDraftNotFoundError) as exc:
            raise _not_found(str(exc)) from exc
        except DraftStateError as exc:
            raise _conflict(exc, "draft_state") from exc
        return _draft_read(view)

    @post("/drafts/{draft_id:uuid}/approve", status_code=200)
    async def approve_letter(
        self,
        project_id: FromPath[uuid.UUID],
        draft_id: FromPath[uuid.UUID],
        mail_service: NamedDependency[MailService],
        current_user: NamedDependency[uuid.UUID],
    ) -> ApprovedLetterRead:
        try:
            view = await mail_service.approve_letter(project_id, current_user, draft_id)
        except (ProjectNotFoundError, MailDraftNotFoundError) as exc:
            raise _not_found(str(exc)) from exc
        except DraftStateError as exc:
            raise _conflict(exc, "draft_state") from exc
        except DocumentValidationError as exc:
            raise ValidationException(
                detail=str(exc), extra={"code": "document_type_invalid"}
            ) from exc
        except PdfRenderError as exc:
            raise HTTPException(
                status_code=HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
                extra={"code": "pdf_render_failed"},
            ) from exc
        return _approved_read(view)

    @post("/drafts/{draft_id:uuid}/discard", status_code=200)
    async def discard_draft(
        self,
        project_id: FromPath[uuid.UUID],
        draft_id: FromPath[uuid.UUID],
        mail_service: NamedDependency[MailService],
        current_user: NamedDependency[uuid.UUID],
    ) -> DraftRead:
        try:
            view = await mail_service.discard_draft(project_id, current_user, draft_id)
        except (ProjectNotFoundError, MailDraftNotFoundError) as exc:
            raise _not_found(str(exc)) from exc
        except DraftStateError as exc:
            raise _conflict(exc, "draft_state") from exc
        return _draft_read(view)

    @post(
        "/drafts/{draft_id:uuid}/send", status_code=200, dto=StrictPydanticDTO[SendBody]
    )
    async def send_draft(
        self,
        project_id: FromPath[uuid.UUID],
        draft_id: FromPath[uuid.UUID],
        data: SendBody,
        mail_service: NamedDependency[MailService],
        current_user: NamedDependency[uuid.UUID],
    ) -> SentEmailRead:
        try:
            view = await mail_service.send_draft(
                project_id, current_user, draft_id, sender=data.sender
            )
        except (ProjectNotFoundError, MailDraftNotFoundError) as exc:
            raise _not_found(str(exc)) from exc
        except DocumentNotFoundError as exc:
            raise _not_found(f"attachment {exc} not found") from exc
        except DraftStateError as exc:
            raise _conflict(exc, "draft_state") from exc
        except MailValidationError as exc:
            raise ValidationException(
                detail=str(exc), extra={"code": "send_validation"}
            ) from exc
        except SendLimitError as exc:
            raise _conflict(exc, exc.code) from exc
        except MailSendError as exc:
            raise HTTPException(
                status_code=HTTP_502_BAD_GATEWAY,
                detail=str(exc),
                extra={"code": "mail_send_failed"},
            ) from exc
        except RowUpdateFailedError as exc:
            # The email went out; only the tracker write failed. The client
            # must refresh the tracker and reconcile, not retry the send.
            raise _conflict(exc, "row_update_failed") from exc
        return _sent_read(view)

    @get("/sent")
    async def list_sent(
        self,
        project_id: FromPath[uuid.UUID],
        mail_service: NamedDependency[MailService],
        current_user: NamedDependency[uuid.UUID],
    ) -> SentMessageList:
        try:
            views = await mail_service.list_messages(project_id, current_user)
        except ProjectNotFoundError as exc:
            raise _not_found(f"project {project_id} not found") from exc
        return SentMessageList(data=[_message_read(v) for v in views])
