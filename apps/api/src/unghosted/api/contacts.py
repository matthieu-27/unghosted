"""Contact endpoints: list with search, create, detail, update, delete (us-7)."""

from __future__ import annotations

import uuid

from litestar import Controller, delete, get, patch, post
from litestar.di import NamedDependency
from litestar.exceptions import NotFoundException, ValidationException
from litestar.params import FromPath, FromQuery
from litestar.status_codes import HTTP_204_NO_CONTENT

from unghosted.api.strict_dto import StrictPydanticDTO
from unghosted.domain.contacts import ContactValidationError
from unghosted.repositories.contacts import ContactNotFoundError
from unghosted.repositories.projects import ProjectNotFoundError
from unghosted.schemas import (
    ContactCreate,
    ContactDetailRead,
    ContactList,
    ContactRead,
    ContactThreadRead,
    ContactUpdate,
)
from unghosted.services.contacts import ContactService, ContactView


def _read(view: ContactView) -> ContactRead:
    return ContactRead(
        id=uuid.UUID(view.id),
        name=view.name,
        role=view.role,
        organization=view.organization,
        email=view.email,
        phone=view.phone,
        profile_url=view.profile_url,
        notes=view.notes,
        linked_row_count=view.linked_row_count,
        created_at=view.created_at,
        updated_at=view.updated_at,
    )


def _project_not_found(project_id: uuid.UUID) -> NotFoundException:
    return NotFoundException(
        detail=f"project {project_id} not found", extra={"code": "not_found"}
    )


def _contact_not_found(contact_id: uuid.UUID) -> NotFoundException:
    return NotFoundException(
        detail=f"contact {contact_id} not found", extra={"code": "not_found"}
    )


def _invalid(exc: ContactValidationError) -> ValidationException:
    return ValidationException(
        detail=str(exc),
        extra={"code": "validation_failed", "field": exc.field},
    )


class ContactController(Controller):
    path = "/projects/{project_id:uuid}/contacts"

    @get()
    async def list_contacts(
        self,
        project_id: FromPath[uuid.UUID],
        contact_service: NamedDependency[ContactService],
        current_user: NamedDependency[uuid.UUID],
        search: FromQuery[str] = "",
    ) -> ContactList:
        """`?search=` filters on name, organization, role and email (us-7
        item 1). An empty term is no filter — what an empty search box means.
        The parameter is not called `query`: Litestar reserves that name for
        the whole query-string MultiDict."""
        try:
            views = await contact_service.list(
                project_id, current_user, query=search or None
            )
        except ProjectNotFoundError as exc:
            raise _project_not_found(project_id) from exc
        return ContactList(data=[_read(view) for view in views])

    @post(status_code=201, dto=StrictPydanticDTO[ContactCreate])
    async def create_contact(
        self,
        project_id: FromPath[uuid.UUID],
        data: ContactCreate,
        contact_service: NamedDependency[ContactService],
        current_user: NamedDependency[uuid.UUID],
    ) -> ContactRead:
        try:
            view = await contact_service.create(
                project_id, current_user, fields=data.model_dump()
            )
        except ProjectNotFoundError as exc:
            raise _project_not_found(project_id) from exc
        except ContactValidationError as exc:
            raise _invalid(exc) from exc
        return _read(view)

    @get("/{contact_id:uuid}")
    async def get_contact(
        self,
        project_id: FromPath[uuid.UUID],
        contact_id: FromPath[uuid.UUID],
        contact_service: NamedDependency[ContactService],
        current_user: NamedDependency[uuid.UUID],
    ) -> ContactDetailRead:
        try:
            detail = await contact_service.get(project_id, current_user, contact_id)
        except ProjectNotFoundError as exc:
            raise _project_not_found(project_id) from exc
        except ContactNotFoundError as exc:
            raise _contact_not_found(contact_id) from exc
        return ContactDetailRead(
            contact=_read(detail.contact),
            linked_row_ids=detail.linked_row_ids,
            threads=[
                ContactThreadRead(
                    id=uuid.UUID(thread.id),
                    recipient=thread.recipient,
                    message_count=thread.message_count,
                    last_message_at=thread.last_message_at,
                )
                for thread in detail.threads
            ],
        )

    @patch("/{contact_id:uuid}", dto=StrictPydanticDTO[ContactUpdate])
    async def update_contact(
        self,
        project_id: FromPath[uuid.UUID],
        contact_id: FromPath[uuid.UUID],
        data: ContactUpdate,
        contact_service: NamedDependency[ContactService],
        current_user: NamedDependency[uuid.UUID],
    ) -> ContactRead:
        # exclude_unset keeps the PATCH contract: only what the client sent
        # is a change, so an explicit null clears and an absent key keeps.
        changes = data.model_dump(exclude_unset=True)
        try:
            view = await contact_service.update(
                project_id, current_user, contact_id, changes=changes
            )
        except ProjectNotFoundError as exc:
            raise _project_not_found(project_id) from exc
        except ContactNotFoundError as exc:
            raise _contact_not_found(contact_id) from exc
        except ContactValidationError as exc:
            raise _invalid(exc) from exc
        return _read(view)

    @delete("/{contact_id:uuid}", status_code=HTTP_204_NO_CONTENT)
    async def delete_contact(
        self,
        project_id: FromPath[uuid.UUID],
        contact_id: FromPath[uuid.UUID],
        contact_service: NamedDependency[ContactService],
        current_user: NamedDependency[uuid.UUID],
    ) -> None:
        """Deletes the contact and its row links. The tracker rows survive:
        the link is a cell, not the row (us-7 item 3)."""
        try:
            await contact_service.delete(project_id, current_user, contact_id)
        except ProjectNotFoundError as exc:
            raise _project_not_found(project_id) from exc
        except ContactNotFoundError as exc:
            raise _contact_not_found(contact_id) from exc
